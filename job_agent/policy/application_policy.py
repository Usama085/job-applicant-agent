"""Pre-submit safety policy for auto applications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_agent.database.models import Job
from job_agent.matching.job_matcher import MatchResult


class PolicyRepository(Protocol):
    def get_global_today_count(self) -> int: ...
    def is_already_applied(self, job_url: str) -> bool: ...


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    status_reason: str


class ApplicationPolicy:
    """Combines caps, duplicate checks, match results, and field confidence."""

    def __init__(
        self,
        repository: PolicyRepository,
        global_daily_limit: int,
        max_unknown_required_fields: int = 0,
    ):
        self.repository = repository
        self.global_daily_limit = global_daily_limit
        self.max_unknown_required_fields = max_unknown_required_fields

    def evaluate(
        self,
        job: Job,
        match_result: MatchResult,
        unknown_required_fields: int,
    ) -> PolicyDecision:
        if self.repository.get_global_today_count() >= self.global_daily_limit:
            return PolicyDecision(False, "Global daily application limit reached")

        if self.repository.is_already_applied(job.job_url):
            return PolicyDecision(False, "Already successfully applied to this job")

        if not match_result.allowed:
            return PolicyDecision(False, match_result.reason)

        if unknown_required_fields > self.max_unknown_required_fields:
            return PolicyDecision(False, f"Unknown required fields: {unknown_required_fields}")

        return PolicyDecision(True, "Allowed")
