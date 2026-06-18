"""SQLite repository for persisting jobs, applications, and run logs."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from job_agent.database.migrations import ensure_schema
from job_agent.database.models import Application, Job
from job_agent.utils.constants import ApplicationStatus, RunStatus

logger = logging.getLogger("job_agent.database.repository")


class ApplicationRepository:
    """CRUD operations for the job agent database."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open database connection and ensure schema exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        ensure_schema(self._conn)
        logger.info("Database connected: %s", self._db_path)

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # --- Jobs ---

    def save_job(self, job: Job) -> int:
        """Insert a job (ignore if duplicate by platform+url). Returns job id."""
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (external_id, platform, title, company, location, job_url,
                 is_easy_apply, is_external, experience_req, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.external_id,
                job.platform,
                job.title,
                job.company,
                job.location,
                job.job_url,
                int(job.is_easy_apply),
                int(job.is_external),
                job.experience_req,
                job.discovered_at.isoformat(),
            ),
        )
        self.conn.commit()

        if cursor.lastrowid and cursor.rowcount > 0:
            return cursor.lastrowid

        # Job already existed, fetch its id
        row = self.conn.execute(
            "SELECT id FROM jobs WHERE platform = ? AND job_url = ?",
            (job.platform, job.job_url),
        ).fetchone()
        return row["id"] if row else 0

    def get_job_by_url(self, platform: str, url: str) -> Job | None:
        """Fetch a job by platform and URL."""
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE platform = ? AND job_url = ?",
            (platform, url),
        ).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def is_already_applied(self, job_url: str) -> bool:
        """Check if we have a successful application for this URL."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE j.job_url = ? AND a.status = ?
            """,
            (job_url, ApplicationStatus.APPLIED.value),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    # --- Applications ---

    def save_application(self, application: Application) -> int:
        """Insert an application record. Returns application id."""
        cursor = self.conn.execute(
            """
            INSERT INTO applications
                (job_id, status, failure_reason, screenshot_path,
                 attempt_number, applied_at, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application.job_id,
                application.status.value,
                application.failure_reason,
                application.screenshot_path,
                application.attempt_number,
                application.applied_at.isoformat(),
                application.duration_ms,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def get_today_count(self, platform: str) -> int:
        """Count of 'Applied' status applications for a platform today."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE j.platform = ? AND a.status = ?
            AND date(a.applied_at) = ?
            """,
            (platform, ApplicationStatus.APPLIED.value, self._today_date()),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_global_today_count(self) -> int:
        """Count successful applications across all platforms for the local day."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM applications
            WHERE status = ? AND date(applied_at) = ?
            """,
            (ApplicationStatus.APPLIED.value, self._today_date()),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_daily_report(self) -> list[dict]:
        """All applications from today with job details for reporting."""
        rows = self.conn.execute(
            """
            SELECT j.title, j.company, j.location, j.platform,
                   a.applied_at, j.job_url, a.status, a.failure_reason
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE date(a.applied_at) = ?
            ORDER BY a.applied_at DESC
            """,
            (self._today_date(),),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_job_match(
        self,
        job_id: int,
        job_description: str,
        match_score: int,
        matched_keywords: list[str],
        location_allowed: bool,
        safety_reason: str,
    ) -> None:
        """Persist local matching and safety metadata for a job."""
        self.conn.execute(
            """
            UPDATE jobs SET
                job_description = ?,
                match_score = ?,
                matched_keywords = ?,
                location_allowed = ?,
                safety_reason = ?
            WHERE id = ?
            """,
            (
                job_description,
                match_score,
                json.dumps(matched_keywords),
                int(location_allowed),
                safety_reason,
                job_id,
            ),
        )
        self.conn.commit()

    # --- Outreach ---

    def save_outreach(
        self,
        job_id: int,
        recipient: str,
        subject: str,
        body: str,
        status: str,
        failure_reason: str | None,
    ) -> int:
        """Insert an employer outreach record. Returns the outreach id."""
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO outreach_emails
                (job_id, recipient, subject, body, status, failure_reason, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                recipient,
                subject,
                body,
                status,
                failure_reason,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def was_email_contacted(self, job_id: int, recipient: str) -> bool:
        """Return whether an outreach record already exists for this job/email."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM outreach_emails
            WHERE job_id = ? AND lower(recipient) = lower(?)
            """,
            (job_id, recipient),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    def get_today_outreach_count(self) -> int:
        """Count sent employer outreach emails for the local day."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM outreach_emails
            WHERE status = 'Sent' AND date(sent_at) = ?
            """,
            (self._today_date(),),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_daily_export_rows(self) -> list[dict]:
        """Rows for the daily XLSX export."""
        rows = self.conn.execute(
            """
            SELECT j.title, j.company, j.location, j.platform, j.job_url,
                   j.is_easy_apply, j.is_external, j.match_score,
                   j.matched_keywords, j.safety_reason,
                   a.applied_at, a.status as application_status,
                   a.failure_reason as application_reason,
                   o.recipient, o.subject, o.body,
                   o.status as outreach_status, o.failure_reason as outreach_reason,
                   o.sent_at
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            LEFT JOIN outreach_emails o ON o.job_id = j.id
            WHERE date(a.applied_at) = ?
            ORDER BY a.applied_at DESC
            """,
            (self._today_date(),),
        ).fetchall()
        return [dict(row) for row in rows]

    # --- Run Logs ---

    def start_run(self, platform: str) -> int:
        """Create a RunLog with status Running. Returns run_log id."""
        cursor = self.conn.execute(
            """
            INSERT INTO run_logs (started_at, platform, status)
            VALUES (?, ?, ?)
            """,
            (datetime.now().isoformat(), platform, RunStatus.RUNNING.value),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def finish_run(
        self,
        run_id: int,
        stats: dict,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        """Update a run log with final stats and status."""
        self.conn.execute(
            """
            UPDATE run_logs SET
                finished_at = ?,
                jobs_found = ?,
                applied_count = ?,
                failed_count = ?,
                skipped_count = ?,
                manual_count = ?,
                error_message = ?,
                status = ?
            WHERE id = ?
            """,
            (
                datetime.now().isoformat(),
                stats.get("found", 0),
                stats.get("applied", 0),
                stats.get("failed", 0),
                stats.get("skipped", 0),
                stats.get("manual", 0),
                error,
                status.value,
                run_id,
            ),
        )
        self.conn.commit()

    # --- Helpers ---

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            external_id=row["external_id"],
            platform=row["platform"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            job_url=row["job_url"],
            is_easy_apply=bool(row["is_easy_apply"]),
            is_external=bool(row["is_external"]),
            experience_req=row["experience_req"],
            job_description=row["job_description"] if "job_description" in row.keys() else None,
            match_score=row["match_score"] if "match_score" in row.keys() else None,
            matched_keywords=json.loads(row["matched_keywords"])
            if "matched_keywords" in row.keys() and row["matched_keywords"]
            else [],
            location_allowed=bool(row["location_allowed"])
            if "location_allowed" in row.keys() and row["location_allowed"] is not None
            else None,
            safety_reason=row["safety_reason"] if "safety_reason" in row.keys() else None,
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
        )

    @staticmethod
    def _today_date() -> str:
        return datetime.now().date().isoformat()
