"""Tests for configuration loading."""

from job_agent.config import Settings


def test_settings_defaults():
    """Test that Settings can be created with defaults (no .env file)."""
    settings = Settings.from_env()
    assert settings.browser_headless is False
    assert settings.browser_slow_mo == 50
    assert settings.linkedin_daily_limit == 12
    assert settings.indeed_daily_limit == 12
    assert "linkedin" in settings.enabled_platforms
    assert "indeed" in settings.enabled_platforms


def test_get_daily_limit():
    settings = Settings.from_env()
    assert settings.get_daily_limit("linkedin") == 12
    assert settings.get_daily_limit("indeed") == 12
    assert settings.get_daily_limit("unknown") == 10


def test_get_rate_limit_rpm():
    settings = Settings.from_env()
    assert settings.get_rate_limit_rpm("linkedin") == 20
    assert settings.get_rate_limit_rpm("indeed") == 15
    assert settings.get_rate_limit_rpm("unknown") == 15


def test_safe_apply_settings_defaults():
    settings = Settings.from_env()
    assert settings.global_daily_application_limit == 30
    assert settings.strict_location_filter is True
    assert settings.min_match_score == 65
    assert settings.dry_run is True
    assert settings.auto_send_employer_emails is False
    assert settings.max_employer_emails_per_day == 10
    assert settings.export_excel_report is True
    assert settings.reports_dir.name == "reports"


def test_target_locations_and_excluded_keywords_are_lists():
    settings = Settings.from_env()
    assert "Lahore" in settings.target_locations
    assert "karachi" in settings.match_excluded_keywords
