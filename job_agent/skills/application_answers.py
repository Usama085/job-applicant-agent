"""Reusable answers for common application questions."""

from __future__ import annotations

import re
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

        if self._is_experience_question(text):
            return str(self.profile.years_of_experience)

        if any(term in text for term in ("visa", "sponsor", "sponsorship")):
            return "Yes" if self.profile.visa_sponsorship_required else "No"

        if any(term in text for term in ("relocat", "move to", "move for")):
            return "Yes" if self.profile.willing_to_relocate else "No"

        if any(term in text for term in ("notice", "serving notice")):
            return self.profile.notice_period

        if any(term in text for term in ("join", "start", "avail")):
            return self.profile.availability_date

        if any(term in text for term in ("salary", "compensation", "expected pay", "ctc")):
            return self.profile.salary_expectation

        if any(term in text for term in ("authorized", "eligible to work", "work auth")):
            return self.profile.work_authorization

        if any(term in text for term in ("degree", "education", "qualification", "university")):
            if self.profile.education_degree:
                return self.profile.education_degree
            return None

        if any(term in text for term in ("graduation", "graduated")):
            if self.profile.graduation_year:
                return str(self.profile.graduation_year)
            return None

        if any(term in text for term in ("github", "portfolio", "website", "personal site")):
            return self.profile.linkedin_url or None

        if any(term in text for term in ("why should we hire", "why hire", "why you")):
            title = job.title if job and job.title else "this role"
            company = job.company if job and job.company else "your team"
            return (
                f"I bring practical {self.profile.current_title} experience, "
                f"a Lahore-based work setup, and a background aligned with {title} "
                f"at {company}. {self.profile.summary}"
            )

        if any(term in text for term in ("describe", "tell us", "explain", "brief")):
            return self.profile.summary

        return None

    @staticmethod
    def _is_experience_question(text: str) -> bool:
        if not any(term in text for term in ("year", "experience", "yoe", "exp")):
            return False
        if any(term in text for term in ("visa", "company", "employer", "notice")):
            return False
        return bool(
            re.search(
                r"how\s+many|years?\s+of|experience\s+with|experience\s+in|"
                r"total\s+experience|relevant\s+experience|work\s+experience|"
                r"number\s+of\s+years|exp\s+in\s+years|\d+\s*years?",
                text,
            )
        )
