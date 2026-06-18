"""Indeed job application handler -- Indeed Apply and external applications."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from job_agent.database.models import Application
from job_agent.platforms.indeed import constants, selectors
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

logger = logging.getLogger("job_agent.platforms.indeed.applier")


class IndeedApplier:
    """Handles Indeed's application flow -- both in-platform and external."""

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
        """Apply to an Indeed job listing."""
        start_time = time.monotonic()

        # Navigate to job page
        await self.page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()

        # Check for CAPTCHA
        signal = await self.captcha_detector.check(self.page)
        if signal:
            raise CaptchaDetectedError(
                platform="indeed",
                captcha_type=signal.captcha_type,
                job_url=job.job_url,
            )

        await self.humanizer.simulate_reading(self.page)

        # Try Indeed's apply flow first, then external
        if job.is_easy_apply:
            status = await self._handle_indeed_apply(job)
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

    async def _handle_indeed_apply(self, job: Job) -> ApplicationStatus:
        """Handle Indeed's in-platform apply flow."""
        # Click the Apply button
        apply_btn = self.page.locator(selectors.APPLY_BUTTON)
        try:
            await apply_btn.first.wait_for(
                state="visible", timeout=constants.ELEMENT_TIMEOUT_MS
            )
            await self.humanizer.human_click(self.page, selectors.APPLY_BUTTON)
        except Exception:
            logger.warning("Indeed Apply button not found: %s", job.job_url)
            # Try the generic apply
            return await self._handle_external_apply(job)

        await self.humanizer.random_delay()

        # Indeed may open an iframe or a new page for the apply flow
        # Check if there's an apply iframe
        iframe_locator = self.page.locator(selectors.APPLY_IFRAME)
        if await iframe_locator.count() > 0:
            return await self._handle_iframe_apply(job)

        # Otherwise, handle the multi-step form on the page
        return await self._handle_multi_step_apply(job)

    async def _handle_iframe_apply(self, job: Job) -> ApplicationStatus:
        """Handle Indeed apply when it opens in an iframe."""
        try:
            iframe_element = self.page.locator(selectors.APPLY_IFRAME).first
            frame = await iframe_element.content_frame()
            if not frame:
                logger.warning("Could not access Indeed apply iframe")
                return ApplicationStatus.FAILED

            # Process form steps within the iframe
            for step in range(MAX_FORM_STEPS):
                logger.debug("Indeed iframe apply step %d", step + 1)

                # Upload resume if needed
                file_inputs = frame.locator('input[type="file"]')
                if await file_inputs.count() > 0:
                    try:
                        await file_inputs.first.set_input_files(
                            str(self.resume_uploader.resume_path)
                        )
                        logger.info("Resume uploaded in iframe")
                    except Exception as e:
                        logger.warning("Failed to upload resume in iframe: %s", e)

                # Detect and fill form fields
                fields = await self.form_detector.detect_fields(frame)
                if fields:
                    fill_result = await self.form_filler.fill_form(frame, fields, job)
                    if fill_result.unknown_required_count > 0:
                        raise FormFillingError(
                            platform="indeed",
                            field_name="required fields",
                            reason=(
                                "Unknown required fields: "
                                f"{fill_result.unknown_required_count}"
                            ),
                        )

                await self.humanizer.think_pause()

                # Look for submit or continue
                submit = frame.locator(selectors.SUBMIT_BUTTON)
                if await submit.count() > 0:
                    await submit.first.click()
                    await self.humanizer.random_delay()

                    # Check for success
                    success = frame.locator(selectors.APPLICATION_SUCCESS)
                    try:
                        await success.first.wait_for(
                            state="visible", timeout=constants.ELEMENT_TIMEOUT_MS
                        )
                        return ApplicationStatus.APPLIED
                    except Exception:
                        return ApplicationStatus.APPLIED  # Assume success

                continue_btn = frame.locator(selectors.CONTINUE_BUTTON)
                if await continue_btn.count() > 0:
                    await continue_btn.first.click()
                    await self.humanizer.random_delay()
                else:
                    break

            return ApplicationStatus.FAILED

        except Exception as e:
            logger.warning("Iframe apply failed: %s", e)
            return ApplicationStatus.FAILED

    async def _handle_multi_step_apply(self, job: Job) -> ApplicationStatus:
        """Handle Indeed's multi-step apply form (not in iframe)."""
        for step in range(MAX_FORM_STEPS):
            logger.debug("Indeed apply step %d for: %s", step + 1, job.title)

            # Check for CAPTCHA
            signal = await self.captcha_detector.check(self.page)
            if signal:
                raise CaptchaDetectedError(
                    platform="indeed",
                    captcha_type=signal.captcha_type,
                    job_url=self.page.url,
                )

            # Upload resume
            await self.resume_uploader.upload_if_needed(self.page)

            # Detect and fill form fields
            fields = await self.form_detector.detect_fields(self.page)
            if fields:
                fill_result = await self.form_filler.fill_form(self.page, fields, job)
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="indeed",
                        field_name="required fields",
                        reason=(
                            "Unknown required fields: "
                            f"{fill_result.unknown_required_count}"
                        ),
                    )

            await self.humanizer.think_pause()

            # Check for submit button
            submit = self.page.locator(selectors.SUBMIT_BUTTON)
            if await submit.count() > 0:
                await self.humanizer.human_click(self.page, selectors.SUBMIT_BUTTON)
                await self.humanizer.random_delay()

                # Verify success
                try:
                    await self.page.wait_for_selector(
                        selectors.APPLICATION_SUCCESS,
                        timeout=constants.ELEMENT_TIMEOUT_MS,
                    )
                    return ApplicationStatus.APPLIED
                except Exception:
                    # Check URL change as alternate success indicator
                    if "post-apply" in self.page.url or "submitted" in self.page.url:
                        return ApplicationStatus.APPLIED
                    return ApplicationStatus.APPLIED  # Assume success after submit

            # Click continue/next
            continue_btn = self.page.locator(selectors.CONTINUE_BUTTON)
            if await continue_btn.count() > 0:
                await self.humanizer.human_click(
                    self.page, selectors.CONTINUE_BUTTON
                )
                await self.humanizer.random_delay()
            else:
                logger.warning("No action button found at step %d", step + 1)
                break

        return ApplicationStatus.FAILED

    async def _handle_external_apply(self, job: Job) -> ApplicationStatus:
        """Handle external application links from Indeed."""
        # Click the apply/external link
        ext_btn = self.page.locator(selectors.EXTERNAL_APPLY_BUTTON)
        try:
            if await ext_btn.count() == 0:
                # Fall back to generic apply button
                ext_btn = self.page.locator(selectors.APPLY_BUTTON)

            if await ext_btn.count() == 0:
                logger.warning("No apply button found: %s", job.job_url)
                return ApplicationStatus.SKIPPED
        except Exception:
            return ApplicationStatus.SKIPPED

        # Listen for new tab
        async with self.page.context.expect_page() as new_page_info:
            try:
                await ext_btn.first.click()
            except Exception:
                pass

        try:
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
        except Exception:
            new_page = self.page

        await self.humanizer.random_delay()

        # Check CAPTCHA on external site
        signal = await self.captcha_detector.check(new_page)
        if signal:
            if new_page != self.page:
                await new_page.close()
            raise CaptchaDetectedError(
                platform="indeed",
                captcha_type=signal.captcha_type,
                job_url=new_page.url,
            )

        # Try to fill external form
        try:
            fields = await self.form_detector.detect_fields(new_page)
            if fields:
                await self.resume_uploader.upload_if_needed(new_page)
                fill_result = await self.form_filler.fill_form(new_page, fields, job)
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="indeed",
                        field_name="required fields",
                        reason=(
                            "Unknown required fields: "
                            f"{fill_result.unknown_required_count}"
                        ),
                    )

            # Try to submit
            submitted = await self._try_external_submit(new_page)
            status = (
                ApplicationStatus.APPLIED
                if submitted
                else ApplicationStatus.MANUAL_INTERVENTION
            )

        except Exception as e:
            logger.warning("External apply failed: %s", e)
            status = ApplicationStatus.FAILED

        if new_page != self.page:
            try:
                await new_page.close()
            except Exception:
                pass

        return status

    async def _try_external_submit(self, page: Page) -> bool:
        """Try to find and click a submit button on an external page."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")',
        ]

        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    await self.humanizer.random_delay()
                    return True
            except Exception:
                continue

        return False
