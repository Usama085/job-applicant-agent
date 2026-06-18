from job_agent.database.models import Job
from job_agent.matching.job_matcher import JobMatcher
from job_agent.platforms.base import SearchQuery
from job_agent.profile.user_profile import UserProfile


def _profile() -> UserProfile:
    return UserProfile(
        first_name="Test",
        last_name="User",
        full_name="Test User",
        email="test@example.com",
        phone="+92-300-1234567",
        location="Lahore, Pakistan",
        linkedin_url="https://linkedin.com/in/test",
        current_title="DevOps Engineer",
        current_company="Example",
        years_of_experience=3,
        summary="DevOps engineer with Docker Kubernetes AWS Terraform CI/CD Linux.",
        cover_letter="Dear {company}, I am interested in {title}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=False,
        notice_period="Immediate",
    )


def test_high_score_for_matching_lahore_devops_job():
    matcher = JobMatcher(min_score=65, excluded_keywords=["karachi"])
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        company="Acme",
        location="Lahore, Pakistan",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform CI/CD Linux DevOps",
        job_description="We need Docker, Kubernetes, AWS, Terraform and CI/CD.",
    )

    assert result.allowed
    assert result.score >= 65
    assert "docker" in result.matched_keywords


def test_rejects_excluded_location_keyword():
    matcher = JobMatcher(min_score=65, excluded_keywords=["karachi"])
    job = Job(
        platform="indeed",
        title="DevOps Engineer",
        company="Acme",
        location="Karachi",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform",
        job_description="Karachi based DevOps role with Docker.",
    )

    assert not result.allowed
    assert "excluded keyword" in result.reason.lower()


def test_rejects_low_score_job():
    matcher = JobMatcher(min_score=65, excluded_keywords=[])
    job = Job(
        platform="linkedin",
        title="Sales Executive",
        company="Acme",
        location="Lahore",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform",
        job_description="Sales role with customer calls.",
    )

    assert not result.allowed
    assert result.score < 65
