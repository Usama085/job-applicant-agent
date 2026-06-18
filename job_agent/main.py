"""Main entry point -- orchestrates the daily job application run."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

import yaml

from job_agent.browser.humanizer import HumanBehavior
from job_agent.browser.session import BrowserSession
from job_agent.captcha.detector import CaptchaDetector
from job_agent.captcha.handler import CaptchaHandler
from job_agent.config import Settings
from job_agent.database.repository import ApplicationRepository
from job_agent.forms.detector import FormDetector
from job_agent.forms.field_mapping import FieldMapping
from job_agent.forms.filler import FormFiller
from job_agent.forms.resume_uploader import ResumeUploader
from job_agent.matching.job_matcher import JobMatcher
from job_agent.matching.location_filter import LocationFilter
from job_agent.matching.resume_parser import ResumeParser, ResumeParseError
from job_agent.notifications.email_client import EmailClient
from job_agent.notifications.reporter import DailyReporter
from job_agent.outreach.email_extractor import EmailExtractor
from job_agent.outreach.email_outreach import EmailOutreach
from job_agent.policy.application_policy import ApplicationPolicy
from job_agent.platforms.base import BasePlatform, SearchQuery
from job_agent.platforms.indeed.platform import IndeedPlatform
from job_agent.platforms.linkedin.platform import LinkedInPlatform
from job_agent.preflight import format_preflight_report, run_preflight
from job_agent.profile.profile_loader import load_profile
from job_agent.reports.excel_reporter import ExcelReporter
from job_agent.utils.constants import RunStatus
from job_agent.utils.exceptions import LoginExpiredError
from job_agent.utils.logger import setup_logging
from job_agent.utils.rate_limiter import RateLimiter
from job_agent.writing.template_writer import TemplateWriter

logger = logging.getLogger("job_agent.main")

PLATFORM_CLASSES: dict[str, type[BasePlatform]] = {
    "linkedin": LinkedInPlatform,
    "indeed": IndeedPlatform,
}


def load_search_queries(
    path: Path | None = None,
    forced_locations: list[str] | None = None,
) -> list[SearchQuery]:
    """Load search queries from YAML config."""
    config_path = path or Path("config/search_queries.yaml")
    if not config_path.exists():
        logger.warning("Search queries config not found: %s", config_path)
        location = forced_locations[0] if forced_locations else "Lahore"
        return [SearchQuery(title="DevOps Engineer", location=location)]

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    queries: list[SearchQuery] = []
    for q in data.get("queries", []):
        locations = forced_locations or q.get("locations", ["Lahore"])
        for location in dict.fromkeys(locations):
            queries.append(
                SearchQuery(
                    title=q.get("title", "DevOps Engineer"),
                    location=location,
                    experience_max_years=q.get("experience_max_years", 3),
                    remote_ok=q.get("remote_ok", True),
                )
            )

    logger.info("Loaded %d search queries", len(queries))
    return queries


async def run_platform(
    platform_name: str,
    settings: Settings,
    profile,
    repository: ApplicationRepository,
    reporter: DailyReporter,
    queries: list[SearchQuery],
    resume_text: str,
) -> dict:
    """Run the full search-and-apply cycle for one platform."""
    PlatformClass = PLATFORM_CLASSES.get(platform_name)
    if not PlatformClass:
        logger.error("Unknown platform: %s", platform_name)
        return {"found": 0, "applied": 0, "failed": 0, "skipped": 0, "manual": 0}

    run_id = repository.start_run(platform_name)
    session = BrowserSession(platform_name, settings)
    stats = {"found": 0, "applied": 0, "failed": 0, "skipped": 0, "manual": 0}

    try:
        await session.start()

        # Initialize shared components
        humanizer = HumanBehavior(
            settings.min_action_delay_ms, settings.max_action_delay_ms
        )
        form_detector = FormDetector()
        field_mapping = FieldMapping()
        form_filler = FormFiller(profile, field_mapping, humanizer)
        resume_uploader = ResumeUploader(settings.resume_path)
        captcha_detector = CaptchaDetector()
        captcha_handler = CaptchaHandler(repository, reporter, session)
        rate_limiter = RateLimiter(settings.get_rate_limit_rpm(platform_name))
        application_policy = ApplicationPolicy(
            repository=repository,
            global_daily_limit=settings.global_daily_application_limit,
            max_unknown_required_fields=settings.max_unknown_required_fields,
        )
        job_matcher = JobMatcher(
            min_score=settings.min_match_score,
            excluded_keywords=settings.match_excluded_keywords,
            required_skills=settings.match_required_skills,
        )
        location_filter = LocationFilter(
            settings.target_locations,
            strict=settings.strict_location_filter,
        )
        template_writer = TemplateWriter()
        email_extractor = EmailExtractor()
        email_outreach = EmailOutreach(repository, reporter.email_client, settings)

        # Create platform instance
        platform = PlatformClass(
            session=session,
            profile=profile,
            repository=repository,
            settings=settings,
            humanizer=humanizer,
            form_detector=form_detector,
            form_filler=form_filler,
            resume_uploader=resume_uploader,
            captcha_detector=captcha_detector,
            captcha_handler=captcha_handler,
            rate_limiter=rate_limiter,
            application_policy=application_policy,
            job_matcher=job_matcher,
            location_filter=location_filter,
            template_writer=template_writer,
            email_extractor=email_extractor,
            email_outreach=email_outreach,
            resume_text=resume_text,
        )

        # Check login
        logged_in = await platform.is_logged_in()
        if not logged_in:
            raise LoginExpiredError(platform_name)

        # Run search and apply
        stats = await platform.run(queries)
        repository.finish_run(run_id, stats, RunStatus.COMPLETED)

    except LoginExpiredError:
        logger.error("%s: session expired, manual login required", platform_name)
        reporter.send_login_expired_alert(platform_name)
        repository.finish_run(run_id, stats, RunStatus.CRASHED, "Login expired")

    except Exception as e:
        logger.exception("%s: unexpected error", platform_name)
        repository.finish_run(run_id, stats, RunStatus.CRASHED, str(e))

    finally:
        await session.stop()

    return stats


async def async_main() -> None:
    """Async entry point for the agent."""
    settings = Settings.from_env()

    setup_logging(
        log_file=settings.log_file,
        log_level=settings.log_level,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )

    logger.info("=" * 60)
    logger.info("AI Job Application Agent starting at %s", datetime.now())
    logger.info("=" * 60)

    preflight = run_preflight(settings)
    for warning in preflight.warnings:
        logger.warning("Preflight warning: %s Hint: %s", warning.message, warning.hint)
    if not preflight.is_ready:
        logger.error("%s", format_preflight_report(preflight))
        sys.exit(1)

    # Load profile and search queries
    try:
        profile = load_profile()
    except (FileNotFoundError, ValueError) as e:
        logger.error("Failed to load profile: %s", e)
        sys.exit(1)

    try:
        resume_text = ResumeParser().parse(settings.resume_path)
    except ResumeParseError as e:
        logger.error("Failed to load resume for matching: %s", e)
        sys.exit(1)

    forced_locations = [settings.target_locations[0]] if settings.strict_location_filter else None
    queries = load_search_queries(forced_locations=forced_locations)
    if not queries:
        logger.error("No search queries configured")
        sys.exit(1)

    # Initialize database
    repository = ApplicationRepository(settings.database_path)
    repository.connect()

    # Initialize email client and reporter
    email_client = EmailClient(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        address=settings.gmail_address,
        app_password=settings.gmail_app_password,
    )
    reporter = DailyReporter(repository, email_client, settings)

    # Randomize platform order for anti-detection
    platforms = list(settings.enabled_platforms)
    random.shuffle(platforms)

    logger.info("Enabled platforms (randomized order): %s", platforms)

    # Run each platform
    all_stats: dict[str, dict] = {}
    for platform_name in platforms:
        if platform_name not in PLATFORM_CLASSES:
            logger.warning("Skipping unknown platform: %s", platform_name)
            continue

        logger.info("--- Starting platform: %s ---", platform_name)
        stats = await run_platform(
            platform_name,
            settings,
            profile,
            repository,
            reporter,
            queries,
            resume_text,
        )
        all_stats[platform_name] = stats
        logger.info("--- Finished platform: %s ---", platform_name)

        # Pause between platforms for anti-detection
        if len(platforms) > 1:
            pause = random.uniform(30, 90)
            logger.info("Pausing %.0fs before next platform", pause)
            await asyncio.sleep(pause)

    # Send daily summary
    try:
        reporter.send_daily_summary()
        logger.info("Daily summary email sent")
    except Exception as e:
        logger.error("Failed to send daily summary: %s", e)

    if settings.export_excel_report:
        try:
            date_slug = datetime.now().strftime("%Y-%m-%d")
            export_rows = repository.get_daily_export_rows()
            report_path = ExcelReporter(settings.reports_dir).write_daily(
                export_rows,
                date_slug,
            )
            logger.info("Excel report exported: %s", report_path)
        except Exception as e:
            logger.error("Failed to export Excel report: %s", e)

    repository.close()

    # Log final summary
    total_applied = sum(s.get("applied", 0) for s in all_stats.values())
    total_failed = sum(s.get("failed", 0) for s in all_stats.values())
    total_manual = sum(s.get("manual", 0) for s in all_stats.values())
    logger.info(
        "Agent run complete. Total: %d applied, %d failed, %d manual intervention",
        total_applied,
        total_failed,
        total_manual,
    )
    logger.info("=" * 60)


def main() -> None:
    """Synchronous entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
