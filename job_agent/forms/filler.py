"""Form auto-filler -- maps detected fields to profile data and fills them."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from job_agent.forms.detector import DetectedField
from job_agent.forms.field_mapping import FieldMapping
from job_agent.profile.user_profile import UserProfile
from job_agent.skills.application_answers import ApplicationAnswerBank

if TYPE_CHECKING:
    from playwright.async_api import Page

    from job_agent.browser.humanizer import HumanBehavior
    from job_agent.database.models import Job

logger = logging.getLogger("job_agent.forms.filler")


@dataclass
class FormFillResult:
    filled_count: int = 0
    unfilled: list[str] = field(default_factory=list)
    unknown_required_count: int = 0


class FormFiller:
    """Maps detected form fields to user profile data and fills them."""

    def __init__(
        self,
        profile: UserProfile,
        field_mapping: FieldMapping,
        humanizer: HumanBehavior,
    ):
        self.profile = profile
        self.mapping = field_mapping
        self.humanizer = humanizer
        self.answer_bank = ApplicationAnswerBank(profile)

    async def fill_form(
        self,
        page: Page,
        fields: list[DetectedField],
        job: Job | None = None,
    ) -> FormFillResult:
        """Fill all detected fields with matching profile data.

        Returns structured fill stats, including unknown required fields.
        """
        unfilled: list[str] = []

        for detected_field in fields:
            if detected_field.field_type == "file":
                # File inputs are handled by ResumeUploader
                continue

            # Skip fields that already have a value
            if detected_field.current_value and detected_field.current_value.strip():
                logger.debug("Skipping pre-filled field: %s", detected_field.identifiers)
                continue

            try:
                filled = await self._fill_field(page, detected_field, job)
                if not filled:
                    identifier = (
                        detected_field.label_text
                        or detected_field.name_attr
                        or detected_field.selector
                    )
                    unfilled.append(identifier)
                    if detected_field.is_required:
                        logger.warning("Could not fill required field: %s", identifier)
                    else:
                        logger.debug("No match for optional field: %s", identifier)
            except Exception as e:
                identifier = (
                    detected_field.label_text
                    or detected_field.name_attr
                    or detected_field.selector
                )
                logger.warning("Error filling field %s: %s", identifier, e)
                unfilled.append(identifier)

        filled_count = len(fields) - len(unfilled)
        required_unfilled = [
            detected_field.label_text
            or detected_field.name_attr
            or detected_field.selector
            for detected_field in fields
            if detected_field.is_required
            and (
                detected_field.label_text
                or detected_field.name_attr
                or detected_field.selector
            )
            in unfilled
        ]
        logger.info("Filled %d/%d fields", filled_count, len(fields))
        return FormFillResult(
            filled_count=filled_count,
            unfilled=unfilled,
            unknown_required_count=len(required_unfilled),
        )

    async def _fill_field(
        self, page: Page, field: DetectedField, job: Job | None
    ) -> bool:
        """Attempt to fill a single field. Returns True if successful."""
        profile_key, value = self.mapping.find_match(
            field.identifiers, self.profile
        )

        if not value:
            value = self.answer_bank.answer_for(field.identifiers, job)
            profile_key = "answer_bank"
            if not value:
                return False

        # Special handling for cover letter with job context
        if profile_key == "cover_letter" and job:
            generated = getattr(job, "generated_cover_letter", None)
            value = generated or self.profile.get_cover_letter_for(
                company=job.company or "your company",
                title=job.title or "the position",
            )

        try:
            if field.field_type in ("text", "email", "tel", "number", "url", "search"):
                await self._fill_text(page, field, value)
            elif field.field_type == "textarea":
                await self._fill_textarea(page, field, value)
            elif field.field_type == "select" or field.field_type == "select-one":
                await self._fill_select(page, field, value)
            elif field.field_type == "checkbox":
                await self._fill_checkbox(page, field, value)
            elif field.field_type == "radio":
                await self._fill_radio(page, field, value)
            else:
                logger.debug("Unhandled field type: %s", field.field_type)
                return False

            logger.debug(
                "Filled field %s (%s) with %s",
                field.label_text or field.name_attr,
                field.field_type,
                profile_key,
            )
            return True

        except Exception as e:
            logger.warning(
                "Failed to fill %s: %s",
                field.label_text or field.name_attr,
                e,
            )
            return False

    async def _fill_text(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Fill a text-type input with human-like typing."""
        await self.humanizer.human_type(page, field.selector, value)

    async def _fill_textarea(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Fill a textarea element."""
        element = page.locator(field.selector)
        await element.click()
        await self.humanizer.micro_pause()
        await element.fill(value)
        await self.humanizer.micro_pause()

    async def _fill_select(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Select an option from a dropdown by fuzzy matching."""
        element = page.locator(field.selector)

        # Try exact match first
        try:
            await element.select_option(label=value)
            return
        except Exception:
            pass

        # Fuzzy match: find the best matching option
        value_lower = value.lower()
        best_match = None
        best_score = 0

        for option in field.options:
            option_lower = option.lower()
            if value_lower in option_lower or option_lower in value_lower:
                score = len(set(value_lower.split()) & set(option_lower.split()))
                if score > best_score:
                    best_score = score
                    best_match = option

        if best_match:
            await element.select_option(label=best_match)
        else:
            # Try selecting first non-empty option if it's a yes/no type
            if value.lower() in ("yes", "true", "1"):
                for opt in field.options:
                    if opt.lower() in ("yes", "true", "1"):
                        await element.select_option(label=opt)
                        return
            elif value.lower() in ("no", "false", "0"):
                for opt in field.options:
                    if opt.lower() in ("no", "false", "0"):
                        await element.select_option(label=opt)
                        return

            logger.debug("No matching option for '%s' in %s", value, field.options)

    async def _fill_checkbox(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Check or uncheck a checkbox based on value."""
        element = page.locator(field.selector)
        should_check = value.lower() in ("yes", "true", "1")
        is_checked = await element.is_checked()

        if should_check and not is_checked:
            await element.check()
        elif not should_check and is_checked:
            await element.uncheck()

    async def _fill_radio(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Select a radio button option by matching value."""
        element = page.locator(field.selector)
        await element.check()
