"""Local deterministic job-to-resume matching."""

from __future__ import annotations

from dataclasses import dataclass, field

from job_agent.database.models import Job
from job_agent.matching.keyword_extractor import KeywordExtractor
from job_agent.platforms.base import SearchQuery
from job_agent.profile.user_profile import UserProfile
from job_agent.skills.job_quality import JobQualitySkill


@dataclass
class MatchResult:
    allowed: bool
    score: int
    matched_keywords: list[str] = field(default_factory=list)
    reason: str = ""


class JobMatcher:
    """Scores job relevance using local keywords and simple deterministic rules."""

    ROLE_KEYWORDS = ("devops", "cloud", "platform", "sre", "site reliability")

    def __init__(
        self,
        min_score: int,
        excluded_keywords: list[str],
        required_skills: list[str] | None = None,
    ):
        self.min_score = min_score
        self.excluded_keywords = [k.lower() for k in excluded_keywords if k]
        self.required_skills = [k.lower() for k in (required_skills or []) if k]
        self.extractor = KeywordExtractor(extra_keywords=self.required_skills)
        self.quality_skill = JobQualitySkill()

    def score(
        self,
        job: Job,
        query: SearchQuery,
        profile: UserProfile,
        resume_text: str,
        job_description: str,
    ) -> MatchResult:
        combined_job_text = " ".join(
            [
                job.title or "",
                job.company or "",
                job.location or "",
                job_description or "",
            ]
        ).lower()

        for excluded in self.excluded_keywords:
            if excluded and excluded in combined_job_text:
                return MatchResult(False, 0, [], f"Excluded keyword found: {excluded}")

        quality = self.quality_skill.evaluate(job, profile, combined_job_text)
        if not quality.allowed:
            return MatchResult(False, 0, [], quality.reason)

        resume_keywords = set(self.extractor.extract(resume_text))
        job_keywords = set(self.extractor.extract(combined_job_text))
        matched = sorted(resume_keywords & job_keywords)

        score = 0

        job_title = (job.title or "").lower()
        query_title = (query.title or "").lower()
        if "devops" in job_title:
            score += 25
        elif any(token in job_title for token in self.ROLE_KEYWORDS):
            score += 15
        elif query_title and query_title in job_title:
            score += 10

        if job_keywords:
            score += min(40, int((len(matched) / max(len(job_keywords), 1)) * 40))

        if resume_keywords:
            score += min(20, int((len(matched) / max(len(resume_keywords), 1)) * 20))

        if "lahore" in (job.location or "").lower():
            score += 10

        years_text = combined_job_text
        if (
            str(profile.years_of_experience) in years_text
            or "entry" in years_text
            or "junior" in years_text
        ):
            score += 5
        elif profile.years_of_experience >= 3 and any(
            term in years_text
            for term in ("2 years", "3 years", "2+ years", "3+ years")
        ):
            score += 5

        missing_required = [skill for skill in self.required_skills if skill not in matched]
        if missing_required:
            return MatchResult(
                False,
                score,
                matched,
                f"Missing required skills: {', '.join(missing_required)}",
            )

        allowed = score >= self.min_score
        reason = (
            "Matched resume threshold"
            if allowed
            else f"Match score {score} below threshold {self.min_score}"
        )
        return MatchResult(allowed, score, matched, reason)
