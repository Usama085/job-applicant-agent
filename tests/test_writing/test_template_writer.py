from job_agent.database.models import Job
from job_agent.profile.user_profile import UserProfile
from job_agent.writing.template_writer import TemplateWriter


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
        summary="DevOps engineer.",
        cover_letter="Dear {company}, I am interested in {title}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=False,
        notice_period="Immediate",
    )


def test_cover_letter_uses_job_context_and_skills():
    writer = TemplateWriter()
    job = Job(platform="linkedin", title="DevOps Engineer", company="Acme", job_url="https://example.com")

    text = writer.cover_letter(_profile(), job, ["docker", "kubernetes", "terraform"])

    assert "Acme" in text
    assert "DevOps Engineer" in text
    assert "docker, kubernetes, terraform" in text
    assert "Lahore" in text


def test_employer_email_has_subject_and_body():
    writer = TemplateWriter()
    job = Job(platform="indeed", title="Cloud Engineer", company="CloudCo", job_url="https://example.com")

    email = writer.employer_email(_profile(), job, ["aws", "linux"])

    assert email.subject == "Application for Cloud Engineer - Test User"
    assert "CloudCo" in email.body
    assert "aws, linux" in email.body
    assert "https://linkedin.com/in/test" in email.body
