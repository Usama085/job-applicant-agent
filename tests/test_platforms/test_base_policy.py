from types import SimpleNamespace

import pytest

from job_agent.database.models import Application, Job
from job_agent.matching.job_matcher import JobMatcher
from job_agent.matching.location_filter import LocationFilter
from job_agent.outreach.email_extractor import EmailExtractor
from job_agent.platforms.base import BasePlatform, SearchQuery, SearchResult
from job_agent.policy.application_policy import ApplicationPolicy
from job_agent.utils.constants import ApplicationStatus
from job_agent.writing.template_writer import TemplateWriter


class DummySettings:
    dry_run = False
    long_break_every_applications = 5
    long_break_minutes = 20
    min_application_delay_minutes = 0
    max_application_delay_minutes = 0
    max_unknown_required_fields = 0

    def get_daily_limit(self, platform: str) -> int:
        return 10


class DummyPlatform(BasePlatform):
    def __init__(self, jobs, description, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jobs = jobs
        self.description = description
        self.apply_called = False

    @property
    def platform_name(self) -> str:
        return "linkedin"

    async def is_logged_in(self) -> bool:
        return True

    async def search_jobs(self, query: SearchQuery) -> SearchResult:
        return SearchResult(jobs=self.jobs, total_found=len(self.jobs), pages_searched=1)

    async def get_job_description(self, job: Job) -> str:
        return self.description

    async def apply_to_job(self, job: Job) -> Application:
        self.apply_called = True
        return Application(job_id=job.id or 0, status=ApplicationStatus.APPLIED)


def _platform(repository, sample_profile, jobs, description, settings=None):
    settings = settings or DummySettings()
    return DummyPlatform(
        jobs,
        description,
        session=SimpleNamespace(),
        profile=sample_profile,
        repository=repository,
        settings=settings,
        humanizer=SimpleNamespace(),
        form_detector=SimpleNamespace(),
        form_filler=SimpleNamespace(),
        resume_uploader=SimpleNamespace(),
        captcha_detector=SimpleNamespace(),
        captcha_handler=SimpleNamespace(),
        rate_limiter=SimpleNamespace(acquire=lambda: _noop()),
        application_policy=ApplicationPolicy(repository, 30),
        job_matcher=JobMatcher(min_score=65, excluded_keywords=["karachi", "islamabad"]),
        location_filter=LocationFilter(["Lahore"], strict=True),
        template_writer=TemplateWriter(),
        email_extractor=EmailExtractor(),
        email_outreach=None,
        resume_text="DevOps Docker Kubernetes AWS Terraform CI/CD Linux",
    )


async def _noop():
    return None


@pytest.mark.asyncio
async def test_run_skips_non_lahore_jobs_before_apply(repository, sample_profile, monkeypatch):
    monkeypatch.setattr("job_agent.platforms.base.random.random", lambda: 1.0)
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        location="Karachi",
        job_url="https://example.com/karachi",
    )
    platform = _platform(repository, sample_profile, [job], "DevOps Docker Kubernetes")

    stats = await platform.run([SearchQuery(title="DevOps Engineer", location="Lahore")])

    assert stats["skipped"] == 1
    assert stats["applied"] == 0
    assert platform.apply_called is False


@pytest.mark.asyncio
async def test_run_dry_run_records_would_apply_without_apply(repository, sample_profile, monkeypatch):
    monkeypatch.setattr("job_agent.platforms.base.random.random", lambda: 1.0)
    settings = DummySettings()
    settings.dry_run = True
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        company="Acme",
        location="Lahore",
        job_url="https://example.com/lahore",
    )
    platform = _platform(
        repository,
        sample_profile,
        [job],
        "We need Docker Kubernetes AWS Terraform CI/CD.",
        settings=settings,
    )

    stats = await platform.run([SearchQuery(title="DevOps Engineer", location="Lahore")])

    assert stats["skipped"] == 1
    assert stats["applied"] == 0
    assert platform.apply_called is False
    report = repository.get_daily_report()
    assert report[0]["status"] == "Skipped"
    assert report[0]["failure_reason"].startswith("Dry run: would apply.")
