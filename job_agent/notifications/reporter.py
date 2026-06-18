"""Daily report generation and notification dispatch."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from job_agent.notifications.templates import (
    captcha_alert_html,
    daily_summary_html,
    login_expired_html,
)

if TYPE_CHECKING:
    from job_agent.config import Settings
    from job_agent.database.repository import ApplicationRepository
    from job_agent.notifications.email_client import EmailClient

logger = logging.getLogger("job_agent.notifications.reporter")


class DailyReporter:
    """Generates and sends daily application summary and alert emails."""

    def __init__(
        self,
        repository: ApplicationRepository,
        email_client: EmailClient,
        settings: Settings,
    ):
        self.repository = repository
        self.email_client = email_client
        self.settings = settings

    def send_daily_summary(self) -> bool:
        """Query today's applications and send a summary email.

        Returns True if the email was sent successfully.
        """
        applications = self.repository.get_daily_report()

        # Calculate stats
        stats = {
            "total": len(applications),
            "applied": sum(1 for a in applications if a["status"] == "Applied"),
            "failed": sum(1 for a in applications if a["status"] == "Failed"),
            "manual": sum(
                1
                for a in applications
                if a["status"] == "Manual Intervention Required"
            ),
            "skipped": sum(
                1
                for a in applications
                if a["status"] in ("Skipped", "Duplicate")
            ),
        }

        date_str = datetime.now().strftime("%A, %B %d, %Y")

        html = daily_summary_html(
            date=date_str,
            applications=applications,
            stats=stats,
        )

        subject = (
            f"Job Agent Report - {date_str} | "
            f"{stats['applied']} Applied, {stats['failed']} Failed"
        )

        success = self.email_client.send(
            to=self.settings.notification_recipient,
            subject=subject,
            html_body=html,
        )

        if success:
            logger.info(
                "Daily summary sent: %d applied, %d failed, %d manual",
                stats["applied"],
                stats["failed"],
                stats["manual"],
            )
        else:
            logger.error("Failed to send daily summary email")

        return success

    def send_captcha_alert(
        self,
        platform: str,
        job_url: str,
        captcha_type: str,
        job_title: str = "Unknown",
        company: str = "Unknown",
    ) -> bool:
        """Send an immediate email alert when CAPTCHA is detected."""
        html = captcha_alert_html(
            platform=platform,
            job_url=job_url,
            captcha_type=captcha_type,
            job_title=job_title,
            company=company,
        )

        subject = f"[URGENT] Manual Intervention Required - {platform.title()} CAPTCHA"

        success = self.email_client.send(
            to=self.settings.notification_recipient,
            subject=subject,
            html_body=html,
        )

        if success:
            logger.info("CAPTCHA alert sent for %s: %s", platform, captcha_type)
        return success

    def send_login_expired_alert(self, platform: str) -> bool:
        """Send an alert that the login session has expired."""
        html = login_expired_html(platform)

        subject = f"[ACTION REQUIRED] {platform.title()} Session Expired"

        success = self.email_client.send(
            to=self.settings.notification_recipient,
            subject=subject,
            html_body=html,
        )

        if success:
            logger.info("Login expired alert sent for %s", platform)
        return success
