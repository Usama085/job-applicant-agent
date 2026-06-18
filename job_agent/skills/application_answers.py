"""Reusable answers for common application questions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_agent.database.models import Job
    from job_agent.profile.user_profile import UserProfile


class ApplicationAnswerBank:
    """Derives concise answers from the local profile without an LLM."""

    def __init__(self, profile: UserProfile):
        self.profile = profile

    def answer_for(self, identifiers: str, job: Job | None = None) -> str | None:
        text = identifiers.lower()

        if any(term in text for term in ("visa", "sponsor", "sponsorship")):
            return "Yes" if self.profile.visa_sponsorship_required else "No"

        if any(term in text for term in ("relocat", "move to", "move for")):
            return "Yes" if self.profile.willing_to_relocate else "No"

        if any(term in text for term in ("notice", "serving notice")):
            return self.profile.notice_period

        if any(term in text for term in ("join", "start", "avail")):
            return self.profile.availability_date

        if any(term in text for term in ("salary", "compensation", "expected pay")):
            return self.profile.salary_expectation

        if any(term in text for term in ("authorized", "eligible to work", "work auth")):
            return self.profile.work_authorization

        if any(term in text for term in ("why should we hire", "why hire", "why you")):
            title = job.title if job and job.title else "this role"
            company = job.company if job and job.company else "your team"
            return (
                f"I bring practical {self.profile.current_title} experience, "
                f"a Lahore-based work setup, and a background aligned with {title} "
                f"at {company}. {self.profile.summary}"
            )

        return None
