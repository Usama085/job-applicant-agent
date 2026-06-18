"""Data models for jobs, applications, and run logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from job_agent.utils.constants import ApplicationStatus, RunStatus


@dataclass
class Job:
    platform: str
    title: str
    job_url: str
    id: int | None = None
    external_id: str | None = None
    company: str | None = None
    location: str | None = None
    is_easy_apply: bool = False
    is_external: bool = False
    experience_req: str | None = None
    job_description: str | None = None
    match_score: int | None = None
    matched_keywords: list[str] = field(default_factory=list)
    location_allowed: bool | None = None
    safety_reason: str | None = None
    generated_cover_letter: str | None = None
    discovered_at: datetime = field(default_factory=datetime.now)


@dataclass
class Application:
    job_id: int
    status: ApplicationStatus
    id: int | None = None
    failure_reason: str | None = None
    screenshot_path: str | None = None
    attempt_number: int = 1
    applied_at: datetime = field(default_factory=datetime.now)
    duration_ms: int | None = None


@dataclass
class RunLog:
    platform: str
    started_at: datetime
    status: RunStatus
    id: int | None = None
    finished_at: datetime | None = None
    jobs_found: int = 0
    applied_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    manual_count: int = 0
    error_message: str | None = None


@dataclass
class OutreachEmail:
    job_id: int
    recipient: str
    subject: str
    body: str
    status: str
    id: int | None = None
    failure_reason: str | None = None
    sent_at: datetime = field(default_factory=datetime.now)
