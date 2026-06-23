"""Shared helpers for identifying the same job across runs."""

from __future__ import annotations

from job_agent.database.models import Job
from job_agent.platforms.indeed.urls import canonical_job_url, extract_job_key


def normalize_job_url(job: Job) -> str:
    """Return a stable job URL where possible."""
    if job.platform == "indeed":
        return canonical_job_url(job.job_url, job.external_id)
    return job.job_url


def job_dedup_key(job: Job) -> str:
    """Stable key for deduplicating search results."""
    if job.external_id:
        return f"{job.platform}:{job.external_id}"

    jk = extract_job_key(job.job_url, None)
    if jk:
        return f"{job.platform}:jk:{jk}"

    url = normalize_job_url(job).split("?")[0].rstrip("/")
    return f"{job.platform}:{url}"
