"""Configuration loader -- reads .env and exposes a typed Settings dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
import os


def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


def _path(val: str) -> Path:
    return Path(val).resolve()


def _int(val: str) -> int:
    return int(val.strip())


def _str_list(val: str) -> list[str]:
    return [s.strip() for s in val.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    # Browser
    browser_headless: bool
    browser_slow_mo: int
    browser_timeout_ms: int
    browser_data_dir: Path

    # Daily limits
    linkedin_daily_limit: int
    indeed_daily_limit: int

    # Email
    smtp_host: str
    smtp_port: int
    gmail_address: str
    gmail_app_password: str
    notification_recipient: str

    # Database
    database_path: Path

    # Resume
    resume_path: Path

    # Logging
    log_level: str
    log_file: Path
    log_max_bytes: int
    log_backup_count: int

    # Rate limiting
    rate_limit_linkedin_rpm: int
    rate_limit_indeed_rpm: int
    min_action_delay_ms: int
    max_action_delay_ms: int

    # Retry
    max_retries: int
    retry_backoff_base: int
    retry_backoff_max: int

    # Screenshots
    screenshot_dir: Path
    screenshot_on_failure: bool

    # Platforms
    enabled_platforms: list[str] = field(default_factory=list)

    # Safe auto-apply
    global_daily_application_limit: int = 30
    target_locations: list[str] = field(default_factory=list)
    strict_location_filter: bool = True
    min_match_score: int = 65
    match_required_skills: list[str] = field(default_factory=list)
    match_excluded_keywords: list[str] = field(default_factory=list)
    dry_run: bool = False

    # Application pacing
    min_application_delay_minutes: int = 3
    max_application_delay_minutes: int = 8
    long_break_every_applications: int = 5
    long_break_minutes: int = 20
    max_unknown_required_fields: int = 0

    # Employer outreach
    auto_send_employer_emails: bool = False
    max_employer_emails_per_day: int = 10
    min_email_delay_minutes: int = 8
    max_email_delay_minutes: int = 20

    # Reports
    export_excel_report: bool = True
    reports_dir: Path = Path("./data/reports").resolve()

    def get_daily_limit(self, platform: str) -> int:
        limits = {
            "linkedin": self.linkedin_daily_limit,
            "indeed": self.indeed_daily_limit,
        }
        return limits.get(platform, 10)

    def get_rate_limit_rpm(self, platform: str) -> int:
        rpms = {
            "linkedin": self.rate_limit_linkedin_rpm,
            "indeed": self.rate_limit_indeed_rpm,
        }
        return rpms.get(platform, 15)

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> Settings:
        """Load settings from .env file and environment variables."""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        def get(key: str, default: str = "") -> str:
            return os.getenv(key, default)

        return cls(
            browser_headless=_bool(get("BROWSER_HEADLESS", "false")),
            browser_slow_mo=_int(get("BROWSER_SLOW_MO", "50")),
            browser_timeout_ms=_int(get("BROWSER_TIMEOUT_MS", "30000")),
            browser_data_dir=_path(get("BROWSER_DATA_DIR", "./data/browser_data")),
            linkedin_daily_limit=_int(get("LINKEDIN_DAILY_LIMIT", "12")),
            indeed_daily_limit=_int(get("INDEED_DAILY_LIMIT", "12")),
            smtp_host=get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=_int(get("SMTP_PORT", "587")),
            gmail_address=get("GMAIL_ADDRESS", ""),
            gmail_app_password=get("GMAIL_APP_PASSWORD", ""),
            notification_recipient=get("NOTIFICATION_RECIPIENT", ""),
            database_path=_path(get("DATABASE_PATH", "./data/db/job_agent.db")),
            resume_path=_path(get("RESUME_PATH", "./data/resumes/resume.pdf")),
            log_level=get("LOG_LEVEL", "INFO"),
            log_file=_path(get("LOG_FILE", "./data/logs/agent.log")),
            log_max_bytes=_int(get("LOG_MAX_BYTES", "5242880")),
            log_backup_count=_int(get("LOG_BACKUP_COUNT", "5")),
            rate_limit_linkedin_rpm=_int(get("RATE_LIMIT_LINKEDIN_RPM", "20")),
            rate_limit_indeed_rpm=_int(get("RATE_LIMIT_INDEED_RPM", "15")),
            min_action_delay_ms=_int(get("MIN_ACTION_DELAY_MS", "800")),
            max_action_delay_ms=_int(get("MAX_ACTION_DELAY_MS", "2500")),
            max_retries=_int(get("MAX_RETRIES", "3")),
            retry_backoff_base=_int(get("RETRY_BACKOFF_BASE", "2")),
            retry_backoff_max=_int(get("RETRY_BACKOFF_MAX", "30")),
            screenshot_dir=_path(get("SCREENSHOT_DIR", "./data/screenshots")),
            screenshot_on_failure=_bool(get("SCREENSHOT_ON_FAILURE", "true")),
            enabled_platforms=_str_list(get("ENABLED_PLATFORMS", "linkedin,indeed")),
            global_daily_application_limit=_int(get("GLOBAL_DAILY_APPLICATION_LIMIT", "30")),
            target_locations=_str_list(
                get(
                    "TARGET_LOCATIONS",
                    "Lahore,Lahore Pakistan,Lahore Punjab,Lahore District",
                )
            ),
            strict_location_filter=_bool(get("STRICT_LOCATION_FILTER", "true")),
            min_match_score=_int(get("MIN_MATCH_SCORE", "65")),
            match_required_skills=_str_list(get("MATCH_REQUIRED_SKILLS", "")),
            match_excluded_keywords=_str_list(
                get(
                    "MATCH_EXCLUDED_KEYWORDS",
                    "internship,unpaid,remote only,karachi,islamabad,rawalpindi",
                )
            ),
            dry_run=_bool(get("DRY_RUN", "true")),
            min_application_delay_minutes=_int(get("MIN_APPLICATION_DELAY_MINUTES", "3")),
            max_application_delay_minutes=_int(get("MAX_APPLICATION_DELAY_MINUTES", "8")),
            long_break_every_applications=_int(get("LONG_BREAK_EVERY_APPLICATIONS", "5")),
            long_break_minutes=_int(get("LONG_BREAK_MINUTES", "20")),
            max_unknown_required_fields=_int(get("MAX_UNKNOWN_REQUIRED_FIELDS", "0")),
            auto_send_employer_emails=_bool(get("AUTO_SEND_EMPLOYER_EMAILS", "false")),
            max_employer_emails_per_day=_int(get("MAX_EMPLOYER_EMAILS_PER_DAY", "10")),
            min_email_delay_minutes=_int(get("MIN_EMAIL_DELAY_MINUTES", "8")),
            max_email_delay_minutes=_int(get("MAX_EMAIL_DELAY_MINUTES", "20")),
            export_excel_report=_bool(get("EXPORT_EXCEL_REPORT", "true")),
            reports_dir=_path(get("REPORTS_DIR", "./data/reports")),
        )
