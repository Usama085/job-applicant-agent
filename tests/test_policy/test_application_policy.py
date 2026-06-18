from dataclasses import dataclass

from job_agent.database.models import Job
from job_agent.matching.job_matcher import MatchResult
from job_agent.policy.application_policy import ApplicationPolicy, PolicyDecision


@dataclass
class FakeRepository:
    global_count: int = 0
    duplicate: bool = False

    def get_global_today_count(self) -> int:
        return self.global_count

    def is_already_applied(self, job_url: str) -> bool:
        return self.duplicate


def test_blocks_when_global_cap_reached():
    policy = ApplicationPolicy(repository=FakeRepository(global_count=30), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "Global daily application limit reached"


def test_blocks_duplicate_successful_application():
    policy = ApplicationPolicy(repository=FakeRepository(duplicate=True), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "Already successfully applied to this job"


def test_blocks_low_match_result():
    policy = ApplicationPolicy(repository=FakeRepository(), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(False, 40, [], "low score"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "low score"


def test_blocks_unknown_required_fields():
    policy = ApplicationPolicy(
        repository=FakeRepository(),
        global_daily_limit=30,
        max_unknown_required_fields=0,
    )
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=1)

    assert not decision.allowed
    assert decision.status_reason == "Unknown required fields: 1"


def test_allows_when_all_gates_pass():
    policy = ApplicationPolicy(repository=FakeRepository(), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert decision == PolicyDecision(True, "Allowed")
