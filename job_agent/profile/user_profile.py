"""User profile data model for auto-filling job applications."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Reference:
    name: str
    title: str
    company: str
    email: str
    phone: str


@dataclass
class UserProfile:
    # Personal
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str

    # Professional
    current_title: str
    current_company: str
    years_of_experience: int
    summary: str

    # Application defaults
    cover_letter: str
    salary_expectation: str
    work_authorization: str
    visa_sponsorship_required: bool
    availability_date: str
    willing_to_relocate: bool
    notice_period: str

    # References
    references: list[Reference] = field(default_factory=list)

    def get_cover_letter_for(self, company: str, title: str) -> str:
        """Return cover letter with placeholders filled.

        Future enhancement: AI-based tailoring per job.
        """
        return (
            self.cover_letter
            .replace("{company}", company)
            .replace("{title}", title)
        )
