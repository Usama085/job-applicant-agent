"""LinkedIn job application handler -- Easy Apply and external applications."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from job_agent.database.models import Application
from job_agent.platforms.linkedin import constants, selectors
from job_agent.utils.constants import MAX_FORM_STEPS, ApplicationStatus
from job_agent.utils.exceptions import CaptchaDetectedError, FormFillingError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from job_agent.browser.humanizer import HumanBehavior
    from job_agent.captcha.detector import CaptchaDetector
    from job_agent.database.models import Job
    from job_agent.forms.detector import FormDetector
    from job_agent.forms.filler import FormFiller
    from job_agent.forms.resume_uploader import ResumeUploader

logger = logging.getLogger("job_agent.platforms.linkedin.applier")


class LinkedInApplier:
    """Handles LinkedIn Easy Apply modal and external application links."""

    def __init__(
        self,
        page: Page,
        humanizer: HumanBehavior,
        form_detector: FormDetector,
        form_filler: FormFiller,
        resume_uploader: ResumeUploader,
        captcha_detector: CaptchaDetector,
    ):
        self.page = page
        self.humanizer = humanizer
        self.form_detector = form_detector
        self.form_filler = form_filler
        self.resume_uploader = resume_uploader
        self.captcha_detector = captcha_detector

    async def apply(self, job: Job) -> Application:
        """Apply to a LinkedIn job. Handles both Easy Apply and external links."""
        start_time = time.monotonic()

        # Navigate to job page
        await self.page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()

        # Check for CAPTCHA
        signal = await self.captcha_detector.check(self.page)
        if signal:
            raise CaptchaDetectedError(
                platform="linkedin",
                captcha_type=signal.captcha_type,
                job_url=job.job_url,
            )

        await self.humanizer.simulate_reading(self.page)

        # Determine apply method
        if job.is_easy_apply:
            status = await self._handle_easy_apply(job)
        else:
            status = await self._handle_external_apply(job)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return Application(
            job_id=job.id or 0,
            status=status,
            applied_at=datetime.now(),
            duration_ms=duration_ms,
            failure_reason=None if status == ApplicationStatus.APPLIED else f"Status: {status.value}",
        )

    async def _handle_easy_apply(self, job: Job) -> ApplicationStatus:
        """Handle the LinkedIn Easy Apply modal flow."""
        # Click Easy Apply button
        easy_apply_btn = self.page.locator(selectors.EASY_APPLY_BUTTON)
        try:
            await easy_apply_btn.first.wait_for(
                state="visible", timeout=constants.ELEMENT_TIMEOUT_MS
            )
            await self.humanizer.human_click(self.page, selectors.EASY_APPLY_BUTTON)
        except Exception:
            logger.warning("Easy Apply button not found for: %s", job.job_url)
            return ApplicationStatus.SKIPPED

        # Wait for modal to appear
        try:
            await self.page.wait_for_selector(
                selectors.MODAL, timeout=constants.MODAL_TIMEOUT_MS
            )
        except Exception:
            logger.warning("Easy Apply modal did not appear for: %s", job.job_url)
            return ApplicationStatus.FAILED

        await self.humanizer.random_delay()

        # Process modal steps
        for step in range(MAX_FORM_STEPS):
            logger.debug("Processing Easy Apply step %d for: %s", step + 1, job.title)

            # Check for CAPTCHA in modal
            signal = await self.captcha_detector.check(self.page)
            if signal:
                raise CaptchaDetectedError(
                    platform="linkedin",
                    captcha_type=signal.captcha_type,
                    job_url=job.job_url,
                )

            # Upload resume if file input exists
            await self.resume_uploader.upload_if_needed(
                self.page, selectors.MODAL_CONTENT
            )

            # Detect and fill form fields
            fields = await self.form_detector.detect_fields(
                self.page, selectors.MODAL_CONTENT
            )
            if fields:
                fill_result = await self.form_filler.fill_form(
                    self.page, fields, job
                )
                if fill_result.unfilled:
                    logger.debug("Unfilled fields: %s", fill_result.unfilled)
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="linkedin",
                        field_name="required fields",
                        reason=(
                            "Unknown required fields: "
                            f"{fill_result.unknown_required_count}"
                        ),
                    )

            await self.humanizer.think_pause()

            # Check for validation errors before proceeding
            error_count = await self.page.locator(selectors.MODAL_ERROR).count()
            if error_count > 0:
                logger.warning(
                    "Form validation errors detected at step %d", step + 1
                )

            # Determine next action
            action = await self._detect_modal_action()

            if action == "submit":
                return await self._click_submit()
            elif action == "review":
                await self._click_review()
                # After review, look for submit button
                await self.humanizer.random_delay()
                return await self._click_submit()
            elif action == "next":
                await self._click_next()
                await self.humanizer.random_delay()
            else:
                logger.warning("No action button found at step %d", step + 1)
                return ApplicationStatus.FAILED

        logger.warning("Exceeded max form steps (%d) for: %s", MAX_FORM_STEPS, job.title)
        await self._dismiss_modal()
        return ApplicationStatus.FAILED

    async def _handle_external_apply(self, job: Job) -> ApplicationStatus:
        """Handle external application links that open company career pages."""
        # Click the external apply button
        apply_btn = self.page.locator(selectors.EXTERNAL_APPLY_BUTTON)
        try:
            await apply_btn.first.wait_for(
                state="visible", timeout=constants.ELEMENT_TIMEOUT_MS
            )
        except Exception:
            logger.warning("Apply button not found for external job: %s", job.job_url)
            return ApplicationStatus.SKIPPED

        # Listen for new tab/popup
        async with self.page.context.expect_page() as new_page_info:
            try:
                await self.humanizer.human_click(
                    self.page, selectors.EXTERNAL_APPLY_BUTTON
                )
            except Exception:
                # Sometimes it navigates in the same tab
                pass

        try:
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
        except Exception:
            # No new tab -- might have navigated in the same tab
            new_page = self.page

        await self.humanizer.random_delay()

        # Check for CAPTCHA on external site
        signal = await self.captcha_detector.check(new_page)
        if signal:
            if new_page != self.page:
                await new_page.close()
            raise CaptchaDetectedError(
                platform="linkedin",
                captcha_type=signal.captcha_type,
                job_url=new_page.url,
            )

        # Attempt to fill the external form
        try:
            fields = await self.form_detector.detect_fields(new_page)
            if fields:
                await self.resume_uploader.upload_if_needed(new_page)
                fill_result = await self.form_filler.fill_form(
                    new_page, fields, job
                )
                logger.info(
                    "External form: filled %d fields, %d unfilled",
                    fill_result.filled_count,
                    len(fill_result.unfilled),
                )
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="linkedin",
                        field_name="required fields",
                        reason=(
                            "Unknown required fields: "
                            f"{fill_result.unknown_required_count}"
                        ),
                    )

            # Look for submit-type button
            submit_clicked = await self._try_external_submit(new_page)
            if submit_clicked:
                status = ApplicationStatus.APPLIED
            else:
                # Could fill but couldn't find submit -- mark as manual
                status = ApplicationStatus.MANUAL_INTERVENTION
                logger.info(
                    "External form filled but submit button not found: %s",
                    new_page.url,
                )

        except Exception as e:
            logger.warning("Failed to handle external application: %s", e)
            status = ApplicationStatus.FAILED

        # Close the external tab if it was opened
        if new_page != self.page:
            try:
                await new_page.close()
            except Exception:
                pass

        return status

    async def _detect_modal_action(self) -> str | None:
        """Detect which action button is available in the modal footer.

        Returns: 'submit', 'review', 'next', or None.
        """
        # Check submit first (highest priority)
        if await self.page.locator(selectors.MODAL_SUBMIT).count() > 0:
            return "submit"

        # Check review
        if await self.page.locator(selectors.MODAL_REVIEW).count() > 0:
            return "review"

        # Check next
        if await self.page.locator(selectors.MODAL_NEXT).count() > 0:
            return "next"

        return None

    async def _click_next(self) -> None:
        """Click the Next button in the Easy Apply modal."""
        await self.humanizer.human_click(self.page, selectors.MODAL_NEXT)
        await self.humanizer.micro_pause()

    async def _click_review(self) -> None:
        """Click the Review button in the Easy Apply modal."""
        await self.humanizer.human_click(self.page, selectors.MODAL_REVIEW)
        await self.humanizer.micro_pause()

    async def _click_submit(self) -> ApplicationStatus:
        """Click the Submit button and verify success."""
        try:
            await self.humanizer.human_click(self.page, selectors.MODAL_SUBMIT)
            await self.humanizer.random_delay()

            # Wait for success indicator
            try:
                await self.page.wait_for_selector(
                    selectors.APPLICATION_SUCCESS,
                    timeout=constants.ELEMENT_TIMEOUT_MS,
                )
                logger.info("Application submitted successfully")
            except Exception:
                # Success toast might appear and disappear quickly
                logger.debug("Success indicator not detected, assuming submission")

            # Dismiss any post-apply modal
            await self._dismiss_modal()
            return ApplicationStatus.APPLIED

        except Exception as e:
            logger.warning("Failed to click submit: %s", e)
            return ApplicationStatus.FAILED

    async def _dismiss_modal(self) -> None:
        """Dismiss the Easy Apply modal or post-apply popup."""
        try:
            dismiss_btn = self.page.locator(selectors.MODAL_DISMISS)
            if await dismiss_btn.count() > 0:
                await dismiss_btn.first.click()
                await self.humanizer.micro_pause()
        except Exception:
            pass

    async def _try_external_submit(self, page: Page) -> bool:
        """Try to find and click a submit button on an external application page."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")',
            'a:has-text("Submit Application")',
        ]

        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    is_visible = await btn.first.is_visible()
                    if is_visible:
                        await btn.first.click()
                        await self.humanizer.random_delay()
                        return True
            except Exception:
                continue

        return False
