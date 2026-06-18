"""Operational readiness checks for local job-agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from job_agent.config import Settings
from job_agent.matching.resume_parser import ResumeParser, ResumeParseError
from job_agent.profile.profile_loader import DEFAULT_PROFILE_PATH, load_profile


PLACEHOLDER_MARKERS = (
    "your.",
    "your_",
    "example.com",
    "xxxx",
    "replace",
    "changeme",
    "todo",
    "tbd",
)


@dataclass(frozen=True)
class PreflightIssue:
    """A single readiness issue found before running the agent."""

    code: str
    message: str
    hint: str
    blocking: bool = True


@dataclass
class PreflightReport:
    """Collection of readiness issues and convenience accessors."""

    issues: list[PreflightIssue] = field(default_factory=list)

    @property
    def blocking_issues(self) -> list[PreflightIssue]:
        return [issue for issue in self.issues if issue.blocking]

    @property
    def warnings(self) -> list[PreflightIssue]:
        return [issue for issue in self.issues if not issue.blocking]

    @property
    def is_ready(self) -> bool:
        return not self.blocking_issues

    def add_blocker(self, code: str, message: str, hint: str) -> None:
        self.issues.append(PreflightIssue(code, message, hint, blocking=True))

    def add_warning(self, code: str, message: str, hint: str) -> None:
        self.issues.append(PreflightIssue(code, message, hint, blocking=False))

    def has_code(self, code: str) -> bool:
        return any(issue.code == code for issue in self.issues)


def run_preflight(
    settings: Settings | None = None,
    profile_path: Path | None = None,
) -> PreflightReport:
    """Check whether the local agent has the required runtime inputs."""
    settings = settings or Settings.from_env()
    profile_path = profile_path or DEFAULT_PROFILE_PATH
    report = PreflightReport()

    _check_profile(profile_path, report)
    _check_resume(settings, report)
    _check_platforms(settings, report)
    _check_notifications(settings, report)
    _check_runtime_dirs(settings, report)

    return report


def format_preflight_report(report: PreflightReport) -> str:
    """Return a human-readable readiness report."""
    lines = ["Job Agent Preflight"]
    lines.append("Status: ready" if report.is_ready else "Status: not ready")

    if report.blocking_issues:
        lines.append("")
        lines.append("Blocking issues:")
        for issue in report.blocking_issues:
            lines.append(f"- {issue.message} ({issue.hint})")

    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        for issue in report.warnings:
            lines.append(f"- {issue.message} ({issue.hint})")

    if report.is_ready and not report.warnings:
        lines.append("- All required inputs are present.")

    return "\n".join(lines)


def _check_profile(profile_path: Path, report: PreflightReport) -> None:
    try:
        load_profile(profile_path)
    except (FileNotFoundError, ValueError) as exc:
        report.add_blocker(
            "profile_invalid",
            f"Profile is missing or invalid: {exc}",
            "fill config/profile.yaml with your real application details",
        )
        return

    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        report.add_blocker(
            "profile_invalid",
            f"Profile YAML could not be read: {exc}",
            "fix config/profile.yaml syntax",
        )
        return

    personal = data.get("personal", {}) or {}
    required_keys = ("first_name", "last_name", "full_name", "email", "phone", "location")
    for key in required_keys:
        value = str(personal.get(key, "")).strip()
        if _looks_placeholder(value):
            report.add_blocker(
                "profile_placeholder",
                f"Profile field '{key}' still looks like a placeholder",
                "replace template values in config/profile.yaml",
            )

    for idx, reference in enumerate(data.get("references", []) or [], start=1):
        email = str((reference or {}).get("email", "")).strip()
        if email and _looks_placeholder(email):
            report.add_warning(
                "reference_placeholder",
                f"Reference #{idx} email looks like a placeholder",
                "remove optional placeholder references or add real reference details",
            )


def _check_resume(settings: Settings, report: PreflightReport) -> None:
    if not settings.resume_path.exists():
        report.add_blocker(
            "resume_missing",
            f"Resume file missing: {settings.resume_path}",
            "place your resume at RESUME_PATH before running the agent",
        )
        return

    try:
        text = ResumeParser().parse(settings.resume_path)
    except ResumeParseError as exc:
        report.add_blocker(
            "resume_invalid",
            f"Resume could not be parsed: {exc}",
            "use a text-extractable PDF, DOCX, or TXT resume",
        )
        return

    if len(text.split()) < 10:
        report.add_warning(
            "resume_short",
            "Resume text is very short after parsing",
            "check that your PDF/DOCX contains selectable text",
        )


def _check_platforms(settings: Settings, report: PreflightReport) -> None:
    known = {"linkedin", "indeed"}
    for platform in settings.enabled_platforms:
        if platform not in known:
            report.add_blocker(
                f"platform_unknown_{platform}",
                f"Unknown enabled platform: {platform}",
                "set ENABLED_PLATFORMS to linkedin, indeed, or both",
            )
            continue

        session_dir = settings.browser_data_dir / platform
        session_files = []
        if session_dir.exists():
            session_files = [path for path in session_dir.rglob("*") if path.is_file()]

        if not session_files:
            report.add_blocker(
                f"session_missing_{platform}",
                f"No saved browser session for {platform}",
                f"run: python scripts/manual_login.py {platform}",
            )


def _check_notifications(settings: Settings, report: PreflightReport) -> None:
    email_values = {
        "GMAIL_ADDRESS": settings.gmail_address,
        "GMAIL_APP_PASSWORD": settings.gmail_app_password,
        "NOTIFICATION_RECIPIENT": settings.notification_recipient,
    }
    missing = [key for key, value in email_values.items() if not value.strip()]
    placeholders = [key for key, value in email_values.items() if _looks_placeholder(value)]

    if missing or placeholders:
        names = ", ".join(missing + placeholders)
        report.add_warning(
            "notifications_unconfigured",
            f"Email notifications are not fully configured: {names}",
            "set Gmail app-password notification values in .env for alerts and reports",
        )


def _check_runtime_dirs(settings: Settings, report: PreflightReport) -> None:
    for path in (
        settings.database_path.parent,
        settings.log_file.parent,
        settings.screenshot_dir,
        settings.reports_dir,
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            report.add_blocker(
                "runtime_dir_unwritable",
                f"Runtime directory cannot be created: {path}",
                str(exc),
            )


def _looks_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def main() -> None:
    report = run_preflight()
    print(format_preflight_report(report))
    raise SystemExit(0 if report.is_ready else 1)


if __name__ == "__main__":
    main()
