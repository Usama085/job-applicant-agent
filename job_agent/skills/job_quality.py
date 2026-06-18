"""Deterministic job quality screening before application attempts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from job_agent.database.models import Job
from job_agent.profile.user_profile import UserProfile


@dataclass(frozen=True)
class QualityResult:
    allowed: bool
    reason: str = "Quality screen passed"


class JobQualitySkill:
    """Rejects high-risk or obviously mismatched jobs before scoring."""

    REJECT_TERMS = (
        "unpaid",
        "volunteer",
        "commission only",
        "commission-only",
        "no salary",
    )

    def evaluate(
        self,
        job: Job,
        profile: UserProfile,
        job_description: str,
    ) -> QualityResult:
        combined = " ".join(
            [job.title or "", job.location or "", job_description or ""]
        ).lower()

        for term in self.REJECT_TERMS:
            if term in combined:
                return QualityResult(False, f"Quality rejected: {term}")

        required_years = self._max_required_years(combined)
        if required_years and required_years > profile.years_of_experience + 2:
            return QualityResult(
                False,
                (
                    "Quality rejected: above profile experience "
                    f"({required_years}+ required vs {profile.years_of_experience} profile)"
                ),
            )

        return QualityResult(True)

    @staticmethod
    def _max_required_years(text: str) -> int | None:
        matches = re.findall(
            r"(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?)",
            text,
            flags=re.IGNORECASE,
        )
        if not matches:
            return None
        return max(int(match) for match in matches)
