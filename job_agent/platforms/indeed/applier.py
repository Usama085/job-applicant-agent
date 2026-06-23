"""Indeed job application handler -- Indeed Apply and external applications."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from job_agent.database.models import Application
from job_agent.platforms.indeed import constants, selectors
from job_agent.platforms.indeed.urls import canonical_job_url
from job_agent.utils.constants import MAX_FORM_STEPS, ApplicationStatus
from job_agent.utils.exceptions import CaptchaDetectedError, FormFillingError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from job_agent.browser.humanizer import HumanBehavior
    from job_agent.captcha.detector import CaptchaDetector
    from job_agent.database.models import Job
    from job_agent.forms.detector import FormDetector
    from job_agent.forms.filler import FormFiller
    from job_agent.forms.resume_uploader import ResumeUploader

logger = logging.getLogger("job_agent.platforms.indeed.applier")

JOB_PAGE_SELECTORS = (
    selectors.APPLY_BUTTON,
    selectors.EXTERNAL_APPLY_BUTTON,
    ".jobsearch-JobComponent",
    "#jobsearch-ViewjobPaneWrapper",
    "h1.jobsearch-JobInfoHeader-title",
    '[data-testid="jobsearch-JobInfoHeader-title"]',
)

APPLY_BUTTON_SELECTORS = (
    selectors.APPLY_BUTTON,
    selectors.EXTERNAL_APPLY_BUTTON,
    'button:has-text("Apply now")',
    'a:has-text("Apply now")',
    '[data-testid="indeedApplyButton"]',
)


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
        job_url = canonical_job_url(job.job_url, job.external_id)

        await self.page.goto(job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()
        await self._wait_for_job_page()

        signal = await self.captcha_detector.check(self.page)
        if signal:
            raise CaptchaDetectedError(
                platform="indeed",
                captcha_type=signal.captcha_type,
                job_url=job_url,
            )

        await self.humanizer.simulate_reading(self.page)
        status = await self._start_apply_flow(job)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return Application(
            job_id=job.id or 0,
            status=status,
            applied_at=datetime.now(),
            duration_ms=duration_ms,
            failure_reason=None if status == ApplicationStatus.APPLIED else f"Status: {status.value}",
        )

    async def _wait_for_job_page(self) -> None:
        """Wait for the job detail panel to render."""
        for _ in range(int(constants.PAGE_LOAD_TIMEOUT_MS / 500)):
            for selector in JOB_PAGE_SELECTORS:
                if await self.page.locator(selector).count() > 0:
                    return
            await asyncio.sleep(0.5)

    async def _find_visible_apply_button(self) -> Locator | None:
        """Return the first visible apply button on the job page."""
        for selector in APPLY_BUTTON_SELECTORS:
            locator = self.page.locator(selector)
            if await locator.count() == 0:
                continue
            try:
                await locator.first.wait_for(
                    state="visible",
                    timeout=constants.ELEMENT_TIMEOUT_MS,
                )
                return locator
            except Exception:
                continue
        return None

    async def _start_apply_flow(self, job: Job) -> ApplicationStatus:
        """Click apply once and route to the correct application flow."""
        apply_btn = await self._find_visible_apply_button()
        if apply_btn is None:
            logger.warning("No apply button found: %s", job.job_url)
            return ApplicationStatus.SKIPPED

        pages_before = len(self.page.context.pages)
        await apply_btn.first.click()
        await self.humanizer.random_delay()

        for _ in range(int(constants.NEW_TAB_WAIT_MS / 500)):
            pages = self.page.context.pages
            if len(pages) > pages_before:
                new_page = pages[-1]
                await new_page.wait_for_load_state("domcontentloaded")
                return await self._handle_external_page(new_page, job)

            if await self.page.locator(selectors.APPLY_IFRAME).count() > 0:
                return await self._handle_iframe_apply(job)

            if await self._indeed_apply_form_visible():
                return await self._handle_multi_step_apply(job)

            await asyncio.sleep(0.5)

        logger.warning("Apply flow did not open for: %s", job.title)
        return ApplicationStatus.FAILED

    async def _handle_iframe_apply(self, job: Job) -> ApplicationStatus:
        """Handle Indeed apply when it opens in an iframe."""
        try:
            iframe_element = self.page.locator(selectors.APPLY_IFRAME).first
            frame = await iframe_element.content_frame()
            if not frame:
                logger.warning("Could not access Indeed apply iframe")
                return ApplicationStatus.FAILED

            for step in range(MAX_FORM_STEPS):
                logger.debug("Indeed iframe apply step %d", step + 1)

                file_inputs = frame.locator('input[type="file"]')
                if await file_inputs.count() > 0:
                    try:
                        await file_inputs.first.set_input_files(
                            str(self.resume_uploader.resume_path)
                        )
                        logger.info("Resume uploaded in iframe")
                    except Exception as e:
                        logger.warning("Failed to upload resume in iframe: %s", e)

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

                submit = frame.locator(selectors.SUBMIT_BUTTON)
                if await submit.count() > 0:
                    await submit.first.click()
                    await self.humanizer.random_delay()
                    return ApplicationStatus.APPLIED

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

            signal = await self.captcha_detector.check(self.page)
            if signal:
                raise CaptchaDetectedError(
                    platform="indeed",
                    captcha_type=signal.captcha_type,
                    job_url=self.page.url,
                )

            await self.resume_uploader.upload_if_needed(self.page)

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

            submit = self.page.locator(selectors.SUBMIT_BUTTON)
            if await submit.count() > 0:
                await self.humanizer.human_click(self.page, selectors.SUBMIT_BUTTON)
                await self.humanizer.random_delay()
                return ApplicationStatus.APPLIED

            continue_btn = self.page.locator(selectors.CONTINUE_BUTTON)
            if await continue_btn.count() > 0:
                await self.humanizer.human_click(self.page, selectors.CONTINUE_BUTTON)
                await self.humanizer.random_delay()
            else:
                logger.warning("No action button found at step %d", step + 1)
                break

        return ApplicationStatus.FAILED

    async def _indeed_apply_form_visible(self) -> bool:
        """Return True when Indeed's on-page smart apply form is open."""
        form_indicators = (
            "#ia-container",
            ".ia-Questions",
            'button[id="ia-continue"]',
            'button[id="ia-submit"]',
            "text=Add your location",
            "text=Submit your application",
        )
        for selector in form_indicators:
            if await self.page.locator(selector).count() > 0:
                return True
        return False

    async def _handle_external_page(self, page: Page, job: Job) -> ApplicationStatus:
        """Fill and submit an employer site opened in a new tab."""
        await self.humanizer.random_delay()

        signal = await self.captcha_detector.check(page)
        if signal:
            if page != self.page:
                await page.close()
            raise CaptchaDetectedError(
                platform="indeed",
                captcha_type=signal.captcha_type,
                job_url=page.url,
            )

        try:
            fields = await self.form_detector.detect_fields(page)
            if fields:
                await self.resume_uploader.upload_if_needed(page)
                fill_result = await self.form_filler.fill_form(page, fields, job)
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="indeed",
                        field_name="required fields",
                        reason=(
                            "Unknown required fields: "
                            f"{fill_result.unknown_required_count}"
                        ),
                    )

            submitted = await self._try_external_submit(page)
            status = (
                ApplicationStatus.APPLIED
                if submitted
                else ApplicationStatus.MANUAL_INTERVENTION
            )

        except Exception as e:
            logger.warning("External apply failed: %s", e)
            status = ApplicationStatus.FAILED

        if page != self.page:
            try:
                await page.close()
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
