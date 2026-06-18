"""Tests for the application repository."""

from job_agent.database.models import Application, Job
from job_agent.database.repository import ApplicationRepository
from job_agent.utils.constants import ApplicationStatus, RunStatus


def test_save_and_retrieve_job(repository: ApplicationRepository):
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        job_url="https://linkedin.com/jobs/view/123",
        company="TestCo",
        location="Lahore",
    )
    job_id = repository.save_job(job)
    assert job_id > 0

    retrieved = repository.get_job_by_url("linkedin", "https://linkedin.com/jobs/view/123")
    assert retrieved is not None
    assert retrieved.title == "DevOps Engineer"
    assert retrieved.company == "TestCo"


def test_duplicate_job_ignored(repository: ApplicationRepository):
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        job_url="https://linkedin.com/jobs/view/123",
    )
    id1 = repository.save_job(job)
    id2 = repository.save_job(job)
    assert id1 == id2


def test_save_application(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="Test", job_url="https://example.com/1")
    job_id = repository.save_job(job)

    app = Application(
        job_id=job_id,
        status=ApplicationStatus.APPLIED,
    )
    app_id = repository.save_application(app)
    assert app_id > 0


def test_is_already_applied(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="Test", job_url="https://example.com/2")
    job_id = repository.save_job(job)

    assert not repository.is_already_applied("https://example.com/2")

    app = Application(job_id=job_id, status=ApplicationStatus.APPLIED)
    repository.save_application(app)

    assert repository.is_already_applied("https://example.com/2")


def test_get_today_count(repository: ApplicationRepository):
    assert repository.get_today_count("linkedin") == 0

    job = Job(platform="linkedin", title="Test", job_url="https://example.com/3")
    job_id = repository.save_job(job)
    app = Application(job_id=job_id, status=ApplicationStatus.APPLIED)
    repository.save_application(app)

    assert repository.get_today_count("linkedin") == 1
    assert repository.get_today_count("indeed") == 0


def test_run_log_lifecycle(repository: ApplicationRepository):
    run_id = repository.start_run("linkedin")
    assert run_id > 0

    stats = {"found": 10, "applied": 5, "failed": 2, "skipped": 3, "manual": 0}
    repository.finish_run(run_id, stats, RunStatus.COMPLETED)


def test_daily_report(repository: ApplicationRepository):
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        job_url="https://example.com/4",
        company="TestCo",
        location="Lahore",
    )
    job_id = repository.save_job(job)
    app = Application(job_id=job_id, status=ApplicationStatus.APPLIED)
    repository.save_application(app)

    report = repository.get_daily_report()
    assert len(report) == 1
    assert report[0]["title"] == "DevOps Engineer"
    assert report[0]["status"] == "Applied"


def test_global_today_count(repository: ApplicationRepository):
    linkedin = Job(platform="linkedin", title="DevOps", job_url="https://example.com/li")
    indeed = Job(platform="indeed", title="DevOps", job_url="https://example.com/in")
    li_id = repository.save_job(linkedin)
    in_id = repository.save_job(indeed)
    repository.save_application(Application(job_id=li_id, status=ApplicationStatus.APPLIED))
    repository.save_application(Application(job_id=in_id, status=ApplicationStatus.APPLIED))

    assert repository.get_global_today_count() == 2


def test_update_job_match_metadata(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com/match")
    job_id = repository.save_job(job)

    repository.update_job_match(
        job_id=job_id,
        job_description="Docker Kubernetes Lahore",
        match_score=82,
        matched_keywords=["docker", "kubernetes"],
        location_allowed=True,
        safety_reason="Matched resume threshold",
    )

    report = repository.get_daily_report()
    assert report == []


def test_outreach_lifecycle(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com/outreach")
    job_id = repository.save_job(job)

    outreach_id = repository.save_outreach(
        job_id=job_id,
        recipient="hr@example.com",
        subject="Application for DevOps",
        body="Dear Hiring Team",
        status="Sent",
        failure_reason=None,
    )

    assert outreach_id > 0
    assert repository.was_email_contacted(job_id, "hr@example.com")
    assert repository.get_today_outreach_count() == 1
