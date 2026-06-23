"""LinkedIn job application handler -- Easy Apply and external applications."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from job_agent.database.models import Application
from job_agent.platforms.linkedin import constants, selectors
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

logger = logging.getLogger("job_agent.platforms.linkedin.applier")

JOB_PAGE_SELECTORS = (
    selectors.JOB_DETAIL_PANEL,
    selectors.JOB_DETAIL_TITLE,
    selectors.EASY_APPLY_BUTTON,
    selectors.APPLY_BUTTON,
    ".jobs-unified-top-card",
)


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

        await self.page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()
        await self._wait_for_job_page()
        await self._wait_for_apply_controls()

        signal = await self.captcha_detector.check(self.page)
        if signal:
            raise CaptchaDetectedError(
                platform="linkedin",
                captcha_type=signal.captcha_type,
                job_url=job.job_url,
            )

        await self.humanizer.simulate_reading(self.page)

        easy_apply_btn = await self._find_easy_apply_button()
        if easy_apply_btn is not None:
            status = await self._handle_easy_apply(job, easy_apply_btn)
        else:
            apply_btn = await self._find_external_apply_button()
            if apply_btn is None:
                logger.warning("No apply button found for: %s", job.job_url)
                duration_ms = int((time.monotonic() - start_time) * 1000)
                return Application(
                    job_id=job.id or 0,
                    status=ApplicationStatus.FAILED,
                    applied_at=datetime.now(),
                    duration_ms=duration_ms,
                    failure_reason="No apply button found",
                )
            status = await self._handle_external_apply(job, apply_btn)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return Application(
            job_id=job.id or 0,
            status=status,
            applied_at=datetime.now(),
            duration_ms=duration_ms,
            failure_reason=None if status == ApplicationStatus.APPLIED else f"Status: {status.value}",
        )

    async def _wait_for_job_page(self) -> None:
        for _ in range(int(constants.PAGE_LOAD_TIMEOUT_MS / 500)):
            for selector in JOB_PAGE_SELECTORS:
                if await self.page.locator(selector).count() > 0:
                    return
            await asyncio.sleep(0.5)

    async def _wait_for_apply_controls(self) -> None:
        """LinkedIn lazy-loads apply links after the job shell renders."""
        deadline = time.monotonic() + (constants.APPLY_BUTTON_WAIT_MS / 1000)
        while time.monotonic() < deadline:
            if await self._find_easy_apply_button() is not None:
                return
            if await self._find_external_apply_button() is not None:
                return
            await asyncio.sleep(0.5)
        await self.page.evaluate("window.scrollTo(0, 0)")

    async def _find_easy_apply_button(self) -> Locator | None:
        strategies = (
            lambda: self.page.locator('a[aria-label*="Easy Apply"]'),
            lambda: self.page.locator('button[aria-label*="Easy Apply"]'),
            lambda: self.page.locator(selectors.EASY_APPLY_BUTTON),
            lambda: self.page.get_by_role("link", name="Easy Apply"),
        )
        return await self._first_visible_locator(strategies)

    async def _find_external_apply_button(self) -> Locator | None:
        strategies = (
            lambda: self.page.locator('a[aria-label*="Apply on company"]'),
            lambda: self.page.locator(selectors.EXTERNAL_APPLY_BUTTON),
            lambda: self.page.locator(selectors.APPLY_BUTTON),
            lambda: self.page.get_by_role("link", name="Apply", exact=True),
        )
        return await self._first_visible_locator(strategies)

    async def _first_visible_locator(self, strategies) -> Locator | None:
        for strategy in strategies:
            try:
                locator = strategy()
                count = await locator.count()
                if count == 0:
                    continue
                for index in range(min(count, 3)):
                    candidate = locator.nth(index)
                    if await candidate.is_visible():
                        return candidate
            except Exception:
                continue
        return None

    async def _find_visible_button(self, selector: str) -> Locator | None:
        locator = self.page.locator(selector)
        if await locator.count() == 0:
            return None
        try:
            await locator.first.wait_for(
                state="visible",
                timeout=constants.ELEMENT_TIMEOUT_MS,
            )
            return locator
        except Exception:
            return None

    async def _handle_easy_apply(self, job: Job, easy_apply_btn: Locator) -> ApplicationStatus:
        """Handle the LinkedIn Easy Apply modal flow."""
        try:
            await easy_apply_btn.click()
        except Exception:
            logger.warning("Easy Apply button not clickable for: %s", job.job_url)
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
                    retry_result = await self.form_filler.fill_form(
                        self.page, fields, job
                    )
                    if retry_result.filled_count > fill_result.filled_count:
                        fill_result = retry_result
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
                    "Form validation errors detected at step %d — retrying fill",
                    step + 1,
                )
                retry_fields = await self.form_detector.detect_fields(
                    self.page, selectors.MODAL_CONTENT
                )
                if retry_fields:
                    await self.form_filler.fill_form(
                        self.page, retry_fields, job
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

    async def _handle_external_apply(
        self,
        job: Job,
        apply_btn: Locator,
    ) -> ApplicationStatus:
        """Handle external application links that open company career pages."""
        pages_before = len(self.page.context.pages)
        try:
            await apply_btn.click()
        except Exception:
            logger.warning("Apply button not clickable for external job: %s", job.job_url)
            return ApplicationStatus.SKIPPED

        await self.humanizer.random_delay()

        new_page = self.page
        for _ in range(int(constants.PAGE_LOAD_TIMEOUT_MS / 500)):
            pages = self.page.context.pages
            if len(pages) > pages_before:
                new_page = pages[-1]
                await new_page.wait_for_load_state("domcontentloaded")
                break
            if self.page.url != job.job_url and new_page is self.page:
                break
            await asyncio.sleep(0.5)

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
        footer = self.page.locator(selectors.MODAL_FOOTER)
        scope = footer if await footer.count() > 0 else self.page

        # Prefer enabled Next/Review before a disabled Submit on multi-step forms.
        for action, selector in (
            ("next", selectors.MODAL_NEXT),
            ("review", selectors.MODAL_REVIEW),
            ("submit", selectors.MODAL_SUBMIT),
        ):
            button = await self._find_actionable_button(scope, selector)
            if button is not None:
                return action

        return None

    async def _find_actionable_button(self, scope, selector: str) -> Locator | None:
        buttons = scope.locator(selector)
        count = await buttons.count()
        for index in range(count):
            button = buttons.nth(index)
            try:
                if await self._button_is_actionable(button):
                    return button
            except Exception:
                continue
        return None

    @staticmethod
    async def _button_is_actionable(button: Locator) -> bool:
        if not await button.is_visible():
            return False
        aria_disabled = await button.get_attribute("aria-disabled")
        if aria_disabled in ("true", "True"):
            return False
        try:
            disabled = await button.is_disabled()
            # LinkedIn keeps buttons clickable while reporting disabled on wrappers.
            if disabled:
                classes = (await button.get_attribute("class")) or ""
                if "artdeco-button--disabled" in classes:
                    return False
        except Exception:
            pass
        return True

    async def _click_modal_button(self, selector: str) -> None:
        """Click a visible, enabled modal footer button."""
        role_names = {
            selectors.MODAL_NEXT: ("Next", "Continue"),
            selectors.MODAL_REVIEW: ("Review",),
            selectors.MODAL_SUBMIT: ("Submit application", "Submit"),
        }.get(selector, ())

        modal = self.page.locator(selectors.MODAL)
        for name in role_names:
            try:
                button = modal.get_by_role("button", name=name, exact=False)
                if await button.count() > 0:
                    candidate = button.first
                    if await candidate.is_visible():
                        await candidate.scroll_into_view_if_needed()
                        await candidate.click(timeout=5000)
                        await self.humanizer.micro_pause()
                        return
            except Exception:
                continue

        footer = self.page.locator(selectors.MODAL_FOOTER)
        scopes = [footer] if await footer.count() > 0 else []
        scopes.append(self.page)

        for scope in scopes:
            button = await self._find_actionable_button(scope, selector)
            if button is None:
                continue
            try:
                await button.scroll_into_view_if_needed()
                await button.click(timeout=5000)
                await self.humanizer.micro_pause()
                return
            except Exception:
                continue

        raise RuntimeError(f"Modal button not clickable: {selector}")

    async def _click_next(self) -> None:
        """Click the Next button in the Easy Apply modal."""
        await self._click_modal_button(selectors.MODAL_NEXT)

    async def _click_review(self) -> None:
        """Click the Review button in the Easy Apply modal."""
        await self._click_modal_button(selectors.MODAL_REVIEW)

    async def _click_submit(self) -> ApplicationStatus:
        """Click the Submit button and verify success."""
        try:
            await self._click_modal_button(selectors.MODAL_SUBMIT)
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
