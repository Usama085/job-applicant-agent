from __future__ import annotations

from pathlib import Path

from job_agent.config import Settings
from job_agent.preflight import format_preflight_report, run_preflight


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "browser_headless": False,
        "browser_slow_mo": 50,
        "browser_timeout_ms": 30000,
        "browser_data_dir": tmp_path / "browser_data",
        "linkedin_daily_limit": 2,
        "indeed_daily_limit": 2,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "gmail_address": "sender@example.com",
        "gmail_app_password": "app-password",
        "notification_recipient": "owner@example.com",
        "database_path": tmp_path / "db" / "job_agent.db",
        "resume_path": tmp_path / "resumes" / "resume.txt",
        "log_level": "INFO",
        "log_file": tmp_path / "logs" / "agent.log",
        "log_max_bytes": 5242880,
        "log_backup_count": 5,
        "rate_limit_linkedin_rpm": 20,
        "rate_limit_indeed_rpm": 15,
        "min_action_delay_ms": 800,
        "max_action_delay_ms": 2500,
        "max_retries": 3,
        "retry_backoff_base": 2,
        "retry_backoff_max": 30,
        "screenshot_dir": tmp_path / "screenshots",
        "screenshot_on_failure": True,
        "enabled_platforms": ["linkedin", "indeed"],
        "global_daily_application_limit": 30,
        "target_locations": ["Lahore"],
        "strict_location_filter": True,
        "min_match_score": 65,
        "match_required_skills": [],
        "match_excluded_keywords": ["karachi"],
        "dry_run": True,
        "min_application_delay_minutes": 0,
        "max_application_delay_minutes": 0,
        "long_break_every_applications": 5,
        "long_break_minutes": 20,
        "max_unknown_required_fields": 0,
        "auto_send_employer_emails": False,
        "max_employer_emails_per_day": 10,
        "min_email_delay_minutes": 8,
        "max_email_delay_minutes": 20,
        "export_excel_report": True,
        "reports_dir": tmp_path / "reports",
    }
    values.update(overrides)
    return Settings(**values)


def _write_profile(path: Path, email: str = "waqas@realmail.test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
personal:
  first_name: Waqas
  last_name: Arif
  full_name: Waqas Arif
  email: {email}
  phone: "+92-300-0000000"
  location: Lahore, Pakistan
  linkedin_url: https://www.linkedin.com/in/waqasarif

professional:
  current_title: DevOps Engineer
  current_company: Current Company
  years_of_experience: 3
  summary: DevOps engineer with cloud and automation experience.

application_defaults:
  cover_letter: "Dear {{company}}, I am interested in {{title}}."
  salary_expectation: Negotiable
  work_authorization: Authorized
  visa_sponsorship_required: false
  availability_date: Immediate
  willing_to_relocate: false
  notice_period: Immediate

references: []
""".strip(),
        encoding="utf-8",
    )


def test_preflight_blocks_missing_resume_and_sessions(tmp_path: Path):
    profile_path = tmp_path / "config" / "profile.yaml"
    _write_profile(profile_path)

    report = run_preflight(_settings(tmp_path), profile_path=profile_path)

    assert not report.is_ready
    assert report.has_code("resume_missing")
    assert report.has_code("session_missing_linkedin")
    assert report.has_code("session_missing_indeed")
    assert "resume" in format_preflight_report(report).lower()


def test_preflight_flags_placeholder_profile_email(tmp_path: Path):
    profile_path = tmp_path / "config" / "profile.yaml"
    _write_profile(profile_path, email="your.email@example.com")
    settings = _settings(tmp_path, enabled_platforms=[])
    settings.resume_path.parent.mkdir(parents=True, exist_ok=True)
    settings.resume_path.write_text("DevOps Docker Kubernetes Lahore", encoding="utf-8")

    report = run_preflight(settings, profile_path=profile_path)

    assert not report.is_ready
    assert report.has_code("profile_placeholder")


def test_preflight_ready_when_required_inputs_exist(tmp_path: Path):
    profile_path = tmp_path / "config" / "profile.yaml"
    _write_profile(profile_path)
    settings = _settings(tmp_path)
    settings.resume_path.parent.mkdir(parents=True, exist_ok=True)
    settings.resume_path.write_text("DevOps Docker Kubernetes Lahore", encoding="utf-8")
    for platform in settings.enabled_platforms:
        session_dir = settings.browser_data_dir / platform
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "Preferences").write_text("{}", encoding="utf-8")

    report = run_preflight(settings, profile_path=profile_path)

    assert report.is_ready
    assert report.blocking_issues == []
