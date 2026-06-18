"""CAPTCHA handling -- abort application and notify user."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from job_agent.captcha.detector import CaptchaSignal
from job_agent.database.models import Application
from job_agent.utils.constants import ApplicationStatus

if TYPE_CHECKING:
    from job_agent.browser.session import BrowserSession
    from job_agent.database.models import Job
    from job_agent.database.repository import ApplicationRepository
    from job_agent.notifications.reporter import DailyReporter

logger = logging.getLogger("job_agent.captcha.handler")


class CaptchaHandler:
    """Handles CAPTCHA detection by aborting, logging, and notifying."""

    def __init__(
        self,
        repository: ApplicationRepository,
        reporter: DailyReporter | None,
        session: BrowserSession,
    ):
        self.repository = repository
        self.reporter = reporter
        self.session = session

    async def handle(
        self,
        signal: CaptchaSignal,
        job: Job,
    ) -> Application:
        """Handle a detected CAPTCHA for a specific job application.

        1. Take a screenshot for debugging
        2. Create an application record with Manual Intervention Required
        3. Send an immediate email alert
        4. Return the application record
        """
        # Take screenshot
        screenshot_path = None
        try:
            path = await self.session.take_screenshot(
                f"captcha_{signal.captcha_type}_{job.id or 'unknown'}"
            )
            screenshot_path = str(path)
        except Exception as e:
            logger.warning("Failed to take CAPTCHA screenshot: %s", e)

        # Create application record
        application = Application(
            job_id=job.id or 0,
            status=ApplicationStatus.MANUAL_INTERVENTION,
            failure_reason=(
                f"CAPTCHA detected: {signal.captcha_type} at {signal.page_url}"
            ),
            screenshot_path=screenshot_path,
        )

        logger.warning(
            "Manual intervention required: %s CAPTCHA at %s (job: %s at %s)",
            signal.captcha_type,
            signal.page_url,
            job.title,
            job.company,
        )

        # Send immediate alert
        if self.reporter:
            try:
                self.reporter.send_captcha_alert(
                    platform=job.platform,
                    job_url=job.job_url,
                    captcha_type=signal.captcha_type,
                    job_title=job.title,
                    company=job.company or "Unknown",
                )
            except Exception as e:
                logger.error("Failed to send CAPTCHA alert email: %s", e)

        return application
