"""Abstract base class for job platform implementations."""

from __future__ import annotations

import logging
import random
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from job_agent.utils.constants import (
    MAX_CONSECUTIVE_FAILURES,
    RANDOM_SKIP_RATE,
    ApplicationStatus,
)

if TYPE_CHECKING:
    from job_agent.browser.humanizer import HumanBehavior
    from job_agent.browser.session import BrowserSession
    from job_agent.captcha.detector import CaptchaDetector
    from job_agent.captcha.handler import CaptchaHandler
    from job_agent.config import Settings
    from job_agent.database.models import Application, Job
    from job_agent.database.repository import ApplicationRepository
    from job_agent.forms.detector import FormDetector
    from job_agent.forms.filler import FormFiller
    from job_agent.forms.resume_uploader import ResumeUploader
    from job_agent.matching.job_matcher import JobMatcher, MatchResult
    from job_agent.matching.location_filter import LocationFilter
    from job_agent.outreach.email_extractor import EmailExtractor
    from job_agent.outreach.email_outreach import EmailOutreach
    from job_agent.policy.application_policy import ApplicationPolicy
    from job_agent.profile.user_profile import UserProfile
    from job_agent.utils.rate_limiter import RateLimiter
    from job_agent.writing.template_writer import TemplateWriter


@dataclass
class SearchQuery:
    """A job search query with filters."""

    title: str
    location: str
    experience_max_years: int = 3
    remote_ok: bool = True


@dataclass
class SearchResult:
    """Results from a job search."""

    jobs: list[Job] = field(default_factory=list)
    total_found: int = 0
    pages_searched: int = 0


class BasePlatform(ABC):
    """Abstract interface that every job platform must implement."""

    def __init__(
        self,
        session: BrowserSession,
        profile: UserProfile,
        repository: ApplicationRepository,
        settings: Settings,
        humanizer: HumanBehavior,
        form_detector: FormDetector,
        form_filler: FormFiller,
        resume_uploader: ResumeUploader,
        captcha_detector: CaptchaDetector,
        captcha_handler: CaptchaHandler,
        rate_limiter: RateLimiter,
        application_policy: ApplicationPolicy,
        job_matcher: JobMatcher,
        location_filter: LocationFilter,
        template_writer: TemplateWriter,
        email_extractor: EmailExtractor,
        email_outreach: EmailOutreach | None,
        resume_text: str,
    ):
        self.session = session
        self.profile = profile
        self.repository = repository
        self.settings = settings
        self.humanizer = humanizer
        self.form_detector = form_detector
        self.form_filler = form_filler
        self.resume_uploader = resume_uploader
        self.captcha_detector = captcha_detector
        self.captcha_handler = captcha_handler
        self.rate_limiter = rate_limiter
        self.application_policy = application_policy
        self.job_matcher = job_matcher
        self.location_filter = location_filter
        self.template_writer = template_writer
        self.email_extractor = email_extractor
        self.email_outreach = email_outreach
        self.resume_text = resume_text
        self.logger = logging.getLogger(f"job_agent.platforms.{self.platform_name}")

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return 'linkedin' or 'indeed'."""
        ...

    @abstractmethod
    async def is_logged_in(self) -> bool:
        """Check if the saved session/cookies are still valid."""
        ...

    @abstractmethod
    async def search_jobs(self, query: SearchQuery) -> SearchResult:
        """Search for jobs matching the query."""
        ...

    @abstractmethod
    async def apply_to_job(self, job: Job) -> Application:
        """Attempt to apply to a single job."""
        ...

    @abstractmethod
    async def get_job_description(self, job: Job) -> str:
        """Load and return visible job detail text for matching."""
        ...

    @property
    def daily_limit(self) -> int:
        return self.settings.get_daily_limit(self.platform_name)

    async def run(self, queries: list[SearchQuery]) -> dict:
        """Full platform run: search, filter, apply up to daily limit.

        Returns stats dict with keys: found, applied, failed, skipped, manual.
        """
        from job_agent.database.models import Application as AppModel
        from job_agent.utils.exceptions import (
            CaptchaDetectedError,
            FormFillingError,
        )

        stats = {"found": 0, "applied": 0, "failed": 0, "skipped": 0, "manual": 0}
        consecutive_failures = 0

        today_count = self.repository.get_today_count(self.platform_name)
        remaining = self.daily_limit - today_count

        if remaining <= 0:
            self.logger.info("Daily limit already reached (%d/%d)", today_count, self.daily_limit)
            return stats

        self.logger.info(
            "Starting %s run: %d applications remaining today",
            self.platform_name,
            remaining,
        )

        all_jobs: list[Job] = []

        # Search phase
        for query in queries:
            await self.rate_limiter.acquire()
            try:
                result = await self.search_jobs(query)
                all_jobs.extend(result.jobs)
                stats["found"] += result.total_found
                self.logger.info(
                    "Found %d jobs for '%s' in '%s'",
                    result.total_found,
                    query.title,
                    query.location,
                )
            except Exception as e:
                self.logger.error("Search failed for '%s': %s", query.title, e)

        # Randomize job order for anti-detection
        random.shuffle(all_jobs)

        # Apply phase
        for job in all_jobs:
            if remaining <= 0:
                self.logger.info("Daily limit reached")
                break

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                self.logger.warning(
                    "Circuit breaker: %d consecutive failures, stopping %s",
                    consecutive_failures,
                    self.platform_name,
                )
                break

            # Anti-detection: randomly skip some jobs
            if random.random() < RANDOM_SKIP_RATE:
                self.logger.debug("Random skip for anti-detection: %s", job.title)
                stats["skipped"] += 1
                continue

            # Save job to DB and check for duplicates
            job_id = self.repository.save_job(job)
            job.id = job_id

            if not self.location_filter.is_allowed(job.location):
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=f"Location rejected: {job.location or 'unknown'}",
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            job_description = await self.get_job_description(job)
            match_result = self.job_matcher.score(
                job=job,
                query=SearchQuery(title=job.title, location=job.location or ""),
                profile=self.profile,
                resume_text=self.resume_text,
                job_description=job_description,
            )
            self.repository.update_job_match(
                job_id=job_id,
                job_description=job_description[:5000],
                match_score=match_result.score,
                matched_keywords=match_result.matched_keywords,
                location_allowed=True,
                safety_reason=match_result.reason,
            )
            job.generated_cover_letter = self.template_writer.cover_letter(
                self.profile,
                job,
                match_result.matched_keywords,
            )

            if self.repository.is_already_applied(job.job_url):
                self.logger.debug("Already applied: %s", job.job_url)
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.DUPLICATE,
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            decision = self.application_policy.evaluate(
                job=job,
                match_result=match_result,
                unknown_required_fields=0,
            )
            if not decision.allowed:
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=decision.status_reason,
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            if self.settings.dry_run:
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=f"Dry run: would apply. Score={match_result.score}",
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            # Rate limit between applications
            await self.rate_limiter.acquire()

            try:
                application = await self.apply_to_job(job)
                self.repository.save_application(application)

                if application.status == ApplicationStatus.APPLIED:
                    stats["applied"] += 1
                    remaining -= 1
                    consecutive_failures = 0
                    self.logger.info(
                        "Applied: '%s' at '%s'", job.title, job.company
                    )
                    await self._maybe_send_employer_email(
                        job,
                        job_description,
                        match_result,
                    )
                    await self._pause_after_application(stats["applied"])
                elif application.status == ApplicationStatus.MANUAL_INTERVENTION:
                    stats["manual"] += 1
                    consecutive_failures = 0  # CAPTCHA isn't a "failure"
                elif application.status == ApplicationStatus.SKIPPED:
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
                    consecutive_failures += 1

            except CaptchaDetectedError as e:
                signal = type("Signal", (), {
                    "captcha_type": e.captcha_type,
                    "element_selector": None,
                    "page_url": e.job_url,
                })()
                from job_agent.captcha.detector import CaptchaSignal
                signal = CaptchaSignal(
                    captcha_type=e.captcha_type,
                    element_selector=None,
                    page_url=e.job_url,
                )
                application = await self.captcha_handler.handle(signal, job)
                self.repository.save_application(application)
                stats["manual"] += 1

            except FormFillingError as e:
                self.logger.warning("Form fill error for '%s': %s", job.title, e)
                try:
                    screenshot = await self.session.take_screenshot(
                        f"form_error_{job.id}"
                    )
                except Exception:
                    screenshot = None
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.FAILED,
                    failure_reason=str(e),
                    screenshot_path=str(screenshot) if screenshot else None,
                )
                self.repository.save_application(app)
                stats["failed"] += 1
                consecutive_failures += 1

            except Exception as e:
                self.logger.error(
                    "Unexpected error applying to '%s': %s", job.title, e
                )
                try:
                    screenshot = await self.session.take_screenshot(
                        f"error_{job.id}"
                    )
                except Exception:
                    screenshot = None
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.FAILED,
                    failure_reason=str(e),
                    screenshot_path=str(screenshot) if screenshot else None,
                )
                self.repository.save_application(app)
                stats["failed"] += 1
                consecutive_failures += 1

        self.logger.info(
            "%s run complete: applied=%d failed=%d skipped=%d manual=%d",
            self.platform_name,
            stats["applied"],
            stats["failed"],
            stats["skipped"],
            stats["manual"],
        )
        return stats

    async def _maybe_send_employer_email(
        self,
        job: Job,
        job_description: str,
        match_result: MatchResult,
    ) -> None:
        """Send optional employer outreach if a visible email is available."""
        if not self.email_outreach:
            return

        emails = self.email_extractor.extract(job_description)
        if not emails:
            return

        generated = self.template_writer.employer_email(
            self.profile,
            job,
            match_result.matched_keywords,
        )
        await self.email_outreach.send_if_allowed(job, emails[0], generated)

    async def _pause_after_application(self, applied_count: int) -> None:
        """Pause after successful applications according to safe pacing settings."""
        every = max(self.settings.long_break_every_applications, 1)
        if applied_count % every == 0:
            pause = self.settings.long_break_minutes * 60
        else:
            pause = random.uniform(
                self.settings.min_application_delay_minutes * 60,
                self.settings.max_application_delay_minutes * 60,
            )
        self.logger.info("Application pacing pause: %.0fs", pause)
        await asyncio.sleep(pause)
