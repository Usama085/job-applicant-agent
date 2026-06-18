"""Database schema creation and version management."""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger("job_agent.database.migrations")

SCHEMA_VERSION = 2

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Jobs discovered during search
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT,
    platform        TEXT NOT NULL CHECK(platform IN ('linkedin', 'indeed')),
    title           TEXT NOT NULL,
    company         TEXT,
    location        TEXT,
    job_url         TEXT NOT NULL,
    is_easy_apply   INTEGER DEFAULT 0,
    is_external     INTEGER DEFAULT 0,
    experience_req  TEXT,
    job_description TEXT,
    match_score     INTEGER,
    matched_keywords TEXT,
    location_allowed INTEGER,
    safety_reason   TEXT,
    discovered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, job_url)
);

-- Application attempts
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    status          TEXT NOT NULL CHECK(status IN (
                        'Applied',
                        'Failed',
                        'Manual Intervention Required',
                        'Skipped',
                        'Duplicate'
                    )),
    failure_reason  TEXT,
    screenshot_path TEXT,
    attempt_number  INTEGER NOT NULL DEFAULT 1,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now')),
    duration_ms     INTEGER
);

-- Run log: one row per platform per daily execution
CREATE TABLE IF NOT EXISTS run_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    platform        TEXT NOT NULL,
    jobs_found      INTEGER DEFAULT 0,
    applied_count   INTEGER DEFAULT 0,
    failed_count    INTEGER DEFAULT 0,
    skipped_count   INTEGER DEFAULT 0,
    manual_count    INTEGER DEFAULT 0,
    error_message   TEXT,
    status          TEXT NOT NULL CHECK(status IN (
                        'Running', 'Completed', 'Crashed'
                    ))
);

-- Optional employer outreach
CREATE TABLE IF NOT EXISTS outreach_emails (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    recipient       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('Sent', 'Failed', 'Skipped')),
    failure_reason  TEXT,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(job_id, recipient)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_run_logs_started ON run_logs(started_at);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_emails(sent_at);
CREATE INDEX IF NOT EXISTS idx_outreach_job_id ON outreach_emails(job_id);
"""

MIGRATION_2_STATEMENTS = [
    "ALTER TABLE jobs ADD COLUMN job_description TEXT",
    "ALTER TABLE jobs ADD COLUMN match_score INTEGER",
    "ALTER TABLE jobs ADD COLUMN matched_keywords TEXT",
    "ALTER TABLE jobs ADD COLUMN location_allowed INTEGER",
    "ALTER TABLE jobs ADD COLUMN safety_reason TEXT",
    """
    CREATE TABLE IF NOT EXISTS outreach_emails (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER NOT NULL REFERENCES jobs(id),
        recipient       TEXT NOT NULL,
        subject         TEXT NOT NULL,
        body            TEXT NOT NULL,
        status          TEXT NOT NULL CHECK(status IN ('Sent', 'Failed', 'Skipped')),
        failure_reason  TEXT,
        sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(job_id, recipient)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_emails(sent_at)",
    "CREATE INDEX IF NOT EXISTS idx_outreach_job_id ON outreach_emails(job_id)",
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist, apply migrations if needed."""
    cursor = conn.cursor()

    # Check if schema_version table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        logger.info("Creating database schema (version %d)", SCHEMA_VERSION)
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
        conn.commit()
        logger.info("Database schema created successfully")
        return

    # Check current version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_version = row[0] if row and row[0] else 0

    if current_version < SCHEMA_VERSION:
        logger.info(
            "Upgrading database schema from version %d to %d",
            current_version,
            SCHEMA_VERSION,
        )
        if current_version < 2:
            for statement in MIGRATION_2_STATEMENTS:
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
        conn.commit()
        logger.info("Database schema upgraded successfully")
    else:
        logger.debug("Database schema is up to date (version %d)", current_version)
