"""Optional paced employer outreach."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_agent.config import Settings
    from job_agent.database.models import Job
    from job_agent.database.repository import ApplicationRepository
    from job_agent.notifications.email_client import EmailClient
    from job_agent.writing.template_writer import GeneratedEmail

logger = logging.getLogger("job_agent.outreach.email_outreach")


class EmailOutreach:
    """Sends employer emails only when enabled, capped, and not duplicated."""

    def __init__(
        self,
        repository: ApplicationRepository,
        email_client: EmailClient,
        settings: Settings,
    ):
        self.repository = repository
        self.email_client = email_client
        self.settings = settings

    async def send_if_allowed(
        self,
        job: Job,
        recipient: str,
        generated: GeneratedEmail,
    ) -> bool:
        if not self.settings.auto_send_employer_emails:
            self.repository.save_outreach(
                job_id=job.id or 0,
                recipient=recipient,
                subject=generated.subject,
                body=generated.body,
                status="Skipped",
                failure_reason="Employer outreach disabled",
            )
            return False

        if self.repository.get_today_outreach_count() >= self.settings.max_employer_emails_per_day:
            self.repository.save_outreach(
                job_id=job.id or 0,
                recipient=recipient,
                subject=generated.subject,
                body=generated.body,
                status="Skipped",
                failure_reason="Daily employer email limit reached",
            )
            return False

        if self.repository.was_email_contacted(job.id or 0, recipient):
            return False

        delay = random.uniform(
            self.settings.min_email_delay_minutes * 60,
            self.settings.max_email_delay_minutes * 60,
        )
        logger.info("Waiting %.0fs before employer outreach email", delay)
        await asyncio.sleep(delay)

        html_body = generated.body.replace("\n", "<br>")
        sent = self.email_client.send(recipient, generated.subject, html_body)
        self.repository.save_outreach(
            job_id=job.id or 0,
            recipient=recipient,
            subject=generated.subject,
            body=generated.body,
            status="Sent" if sent else "Failed",
            failure_reason=None if sent else "SMTP send failed",
        )
        return sent
