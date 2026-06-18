"""Local deterministic application text generation."""

from __future__ import annotations

from dataclasses import dataclass

from job_agent.database.models import Job
from job_agent.profile.user_profile import UserProfile


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body: str


class TemplateWriter:
    """Generates professional text from local templates, without any LLM."""

    def cover_letter(
        self,
        profile: UserProfile,
        job: Job,
        matched_skills: list[str],
    ) -> str:
        skills = self._skills_text(matched_skills)
        company = job.company or "your company"
        title = job.title or "the role"
        return (
            f"Dear Hiring Team,\n\n"
            f"I am applying for the {title} role at {company}. My background matches "
            f"your requirements in {skills}, and I have hands-on experience supporting "
            f"cloud infrastructure, automation, CI/CD pipelines, and production operations.\n\n"
            f"I am based in Lahore and would welcome the opportunity to contribute to "
            f"your engineering team.\n\n"
            f"Regards,\n"
            f"{profile.full_name}"
        )

    def employer_email(
        self,
        profile: UserProfile,
        job: Job,
        matched_skills: list[str],
    ) -> GeneratedEmail:
        title = job.title or "the role"
        company = job.company or "your company"
        skills = self._skills_text(matched_skills)
        subject = f"Application for {title} - {profile.full_name}"
        body = (
            f"Dear Hiring Team,\n\n"
            f"I recently applied for the {title} role at {company}. My experience aligns "
            f"with the role, especially around {skills}.\n\n"
            f"I am based in Lahore and available to discuss how I can contribute to your "
            f"engineering team. You can review my profile here: {profile.linkedin_url}\n\n"
            f"Regards,\n"
            f"{profile.full_name}\n"
            f"{profile.phone}\n"
            f"{profile.email}"
        )
        return GeneratedEmail(subject=subject, body=body)

    @staticmethod
    def _skills_text(matched_skills: list[str]) -> str:
        clean = [skill.strip() for skill in matched_skills if skill.strip()]
        return ", ".join(clean[:6]) if clean else "DevOps engineering and automation"
