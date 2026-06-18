from job_agent.database.models import Job
from job_agent.matching.job_matcher import JobMatcher
from job_agent.platforms.base import SearchQuery
from job_agent.skills.job_quality import JobQualitySkill


def test_job_quality_rejects_roles_far_above_profile(sample_profile):
    skill = JobQualitySkill()
    job = Job(
        platform="linkedin",
        title="Principal DevOps Engineer",
        location="Lahore",
        job_url="https://example.com/principal",
    )

    result = skill.evaluate(job, sample_profile, "Requires 8+ years of production experience.")

    assert not result.allowed
    assert "above profile experience" in result.reason


def test_job_matcher_uses_quality_skill_before_scoring(sample_profile):
    matcher = JobMatcher(min_score=65, excluded_keywords=[])
    job = Job(
        platform="linkedin",
        title="Senior DevOps Engineer",
        location="Lahore",
        job_url="https://example.com/senior",
    )

    result = matcher.score(
        job=job,
        query=SearchQuery(title="DevOps Engineer", location="Lahore"),
        profile=sample_profile,
        resume_text="DevOps Docker Kubernetes AWS Terraform CI/CD Linux",
        job_description="Requires 7+ years of DevOps experience with Docker Kubernetes AWS Terraform.",
    )

    assert not result.allowed
    assert "above profile experience" in result.reason
