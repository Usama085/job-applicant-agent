"""Form auto-filler -- maps detected fields to profile data and fills them."""

from __future__ import annotations

import logging
import re
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
        filled_count = 0
        fillable_fields = [
            detected_field
            for detected_field in fields
            if detected_field.field_type != "file"
        ]

        for detected_field in fillable_fields:
            # Skip fields that already have a value
            if detected_field.current_value and detected_field.current_value.strip():
                logger.debug("Skipping pre-filled field: %s", detected_field.identifiers)
                filled_count += 1
                continue

            try:
                filled = await self._fill_field(page, detected_field, job)
                if filled:
                    filled_count += 1
                else:
                    identifier = (
                        detected_field.label_text
                        or detected_field.name_attr
                        or detected_field.id_attr
                        or detected_field.selector
                    )
                    if detected_field.label_text:
                        identifier = f"{detected_field.label_text} ({detected_field.id_attr or 'no-id'})"
                    unfilled.append(identifier)
                    if detected_field.is_required:
                        logger.warning(
                            "Could not fill required field: %s (type=%s)",
                            identifier,
                            detected_field.field_type,
                        )
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

        required_unfilled = [
            detected_field.label_text
            or detected_field.name_attr
            or detected_field.selector
            for detected_field in fillable_fields
            if detected_field.is_required
            and (
                detected_field.label_text
                or detected_field.name_attr
                or detected_field.selector
            )
            in unfilled
        ]
        if unfilled:
            logger.info(
                "Unfilled fields: %s",
                ", ".join(unfilled[:5]),
            )
        logger.info("Filled %d/%d fields", filled_count, len(fillable_fields))
        return FormFillResult(
            filled_count=filled_count,
            unfilled=unfilled,
            unknown_required_count=len(required_unfilled),
        )

    async def _fill_field(
        self, page: Page, field: DetectedField, job: Job | None
    ) -> bool:
        """Attempt to fill a single field. Returns True if successful."""
        identifiers = await self._field_identifiers(page, field)
        profile_key, value = self.mapping.find_match(identifiers, self.profile)

        if not value:
            value = self.answer_bank.answer_for(identifiers, job)
            profile_key = "answer_bank"

        if not value:
            value = self._guess_linkedin_fallback(identifiers, field)
            profile_key = "linkedin_fallback"

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
            if field.aria_role == "combobox" or field.field_type == "combobox":
                await self._fill_combobox(page, field, value)
            elif field.field_type in ("text", "email", "tel", "number", "url", "search"):
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
                await self._fill_text(page, field, value)

            if field.aria_role == "combobox" or field.field_type == "combobox":
                if not await self._field_has_value(page, field):
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

    async def _field_identifiers(self, page: Page, field: DetectedField) -> str:
        """Build the best possible label string for heuristic matching."""
        if field.label_text and len(field.label_text.strip()) > 3:
            return field.identifiers

        try:
            surrounding = await page.evaluate(
                """
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return '';
                    const group = el.closest(
                        '.fb-dash-form-element, .jobs-easy-apply-form-element, ' +
                        '.artdeco-form-element, fieldset, [data-test-form-element]'
                    );
                    if (!group) return '';
                    const label = group.querySelector(
                        '.fb-dash-form-element__label, .artdeco-form-element__label, ' +
                        '[data-test-text-form-input-label], .jobs-easy-apply-form-section__label'
                    );
                    if (label) return label.textContent.trim();
                    const clone = group.cloneNode(true);
                    clone.querySelectorAll('input, textarea, select, button, svg')
                        .forEach((node) => node.remove());
                    return clone.textContent.replace(/\\s+/g, ' ').trim().slice(0, 300);
                }
                """,
                field.selector,
            )
        except Exception:
            surrounding = ""

        parts = [field.label_text, field.placeholder, field.name_attr, surrounding]
        return " ".join(part for part in parts if part).lower()

    def _guess_linkedin_fallback(
        self, identifiers: str, field: DetectedField
    ) -> str | None:
        """Last-resort answers for LinkedIn Easy Apply fields with React-only ids."""
        text = identifiers.lower()
        if self.answer_bank._is_experience_question(text):
            return str(self.profile.years_of_experience)

        if field.field_type in {"number", "combobox"} or field.aria_role == "combobox":
            if any(term in text for term in ("year", "experience", "skill", "how many")):
                return str(self.profile.years_of_experience)

        if field.field_type == "tel" or "phone" in text or "mobile" in text:
            return self.profile.phone
        if field.field_type == "email" or "email" in text:
            return self.profile.email
        if "city" in text or "location" in text:
            return self.profile.location
        if "country code" in text or ("phone" in text and "code" in text):
            return "Pakistan (+92)"

        return None

    async def _field_has_value(self, page: Page, field: DetectedField) -> bool:
        try:
            value = await page.locator(field.selector).input_value()
            return bool(value and value.strip())
        except Exception:
            return False

    async def _fill_text(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Fill a text-type input with human-like typing."""
        element = page.locator(field.selector)
        await element.scroll_into_view_if_needed()
        await element.click()
        await self.humanizer.micro_pause()
        try:
            await element.fill(value)
        except Exception:
            await self.humanizer.human_type(page, field.selector, value)
        await self.humanizer.micro_pause()

    async def _fill_combobox(
        self, page: Page, field: DetectedField, value: str
    ) -> None:
        """Fill LinkedIn/Indeed typeahead combobox fields."""
        element = page.locator(field.selector)
        await element.scroll_into_view_if_needed()
        await element.click()
        await self.humanizer.micro_pause()

        search_terms = [value]
        if "pakistan" in value.lower():
            search_terms.extend(["Pakistan", "+92", "Pakistan (+92)"])
        if value.isdigit():
            search_terms.append(value)

        for term in search_terms:
            await element.fill("")
            await element.fill(term)
            await self.humanizer.micro_pause()

            option_selectors = [
                f'[role="option"]:has-text("{term}")',
                f'li[role="option"]:has-text("{term}")',
                '.basic-typeahead__selectable',
                '[role="option"]',
            ]
            for selector in option_selectors:
                options = page.locator(selector)
                count = await options.count()
                for index in range(min(count, 5)):
                    option = options.nth(index)
                    try:
                        if not await option.is_visible():
                            continue
                        text = (await option.inner_text()).strip()
                        if term.lower() in text.lower() or (
                            "pakistan" in value.lower() and "pakistan" in text.lower()
                        ):
                            await option.click()
                            await self.humanizer.micro_pause()
                            return
                    except Exception:
                        continue

            await element.press("ArrowDown")
            await self.humanizer.micro_pause()
            await element.press("Enter")
            if await self._field_has_value(page, field):
                return

        await self.humanizer.micro_pause()

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
        """Select a radio button option by matching value or label text."""
        value_lower = value.lower()
        group_name = field.name_attr
        if group_name:
            radios = page.locator(f'input[type="radio"][name="{group_name}"]')
            count = await radios.count()
            for index in range(count):
                radio = radios.nth(index)
                radio_value = (await radio.get_attribute("value") or "").lower()
                radio_id = await radio.get_attribute("id")
                label_text = ""
                if radio_id:
                    label = page.locator(f'label[for="{radio_id}"]')
                    if await label.count() > 0:
                        label_text = (await label.inner_text()).lower()
                haystack = f"{radio_value} {label_text}"
                if value_lower in haystack or haystack in value_lower:
                    await radio.check()
                    return
                if value_lower.isdigit() and label_text:
                    years = int(value_lower)
                    if self._radio_matches_years(label_text, years):
                        await radio.check()
                        return

        element = page.locator(field.selector)
        await element.check()

    @staticmethod
    def _radio_matches_years(label_text: str, years: int) -> bool:
        """Match radio labels like '1-3 years' or '3+ years' to profile years."""
        numbers = [int(match) for match in re.findall(r"\d+", label_text)]
        if not numbers:
            return False
        if "+" in label_text or "more than" in label_text:
            return years >= numbers[0]
        if len(numbers) >= 2:
            return numbers[0] <= years <= numbers[-1]
        return years == numbers[0]
