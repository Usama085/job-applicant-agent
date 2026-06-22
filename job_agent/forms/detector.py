"""Form field detection -- scans pages for input elements and classifies them."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("job_agent.forms.detector")


@dataclass
class DetectedField:
    """A single form field detected on a page."""

    selector: str
    field_type: str  # text, email, tel, select, radio, checkbox, file, textarea, number
    label_text: str | None = None
    name_attr: str | None = None
    id_attr: str | None = None
    placeholder: str | None = None
    is_required: bool = False
    current_value: str | None = None
    options: list[str] = field(default_factory=list)  # For select/radio
    aria_role: str | None = None

    @property
    def identifiers(self) -> str:
        """Combined string of all identifying attributes for matching."""
        parts = []
        if self.label_text:
            parts.append(self.label_text)
        if self.name_attr:
            parts.append(self.name_attr)
        if self.id_attr:
            parts.append(self.id_attr)
        if self.placeholder:
            parts.append(self.placeholder)
        return " ".join(parts).lower()


class FormDetector:
    """Scans a page or container for form fields and classifies them."""

    async def detect_fields(
        self, page: Page, container_selector: str = "body"
    ) -> list[DetectedField]:
        """Detect all form fields within a container element.

        Finds input, select, and textarea elements, then classifies each
        by label text, attributes, and type.
        """
        fields: list[DetectedField] = []

        # Detect all form elements in one JS evaluation
        raw_fields = await page.evaluate(
            """
            (containerSelector) => {
                const container = document.querySelector(containerSelector) || document.body;

                const getGroupLabel = (group, input) => {
                    if (!group) return '';
                    const explicit = group.querySelector(
                        '.fb-dash-form-element__label, .artdeco-form-element__label, ' +
                        '[data-test-text-form-input-label], .jobs-easy-apply-form-section__label, ' +
                        'span.artdeco-form-element__label, legend, label'
                    );
                    if (explicit) {
                        const text = explicit.textContent.trim();
                        if (text) return text;
                    }
                    const clone = group.cloneNode(true);
                    clone.querySelectorAll(
                        'input, textarea, select, button, option, svg'
                    ).forEach((node) => node.remove());
                    const text = clone.textContent.replace(/\\s+/g, ' ').trim();
                    return text.length <= 300 ? text : text.slice(0, 300);
                };

                const buildSelector = (el) => {
                    if (el.id) {
                        return `[id="${el.id.replace(/"/g, '\\\\"')}"]`;
                    }
                    if (el.name) {
                        const tag = el.tagName.toLowerCase();
                        return `${tag}[name="${el.name.replace(/"/g, '\\\\"')}"]`;
                    }
                    const tag = el.tagName.toLowerCase();
                    const siblings = Array.from(
                        (el.closest(containerSelector) || container).querySelectorAll(tag)
                    );
                    const idx = siblings.indexOf(el);
                    return `${tag}:nth-of-type(${idx + 1})`;
                };

                const seen = new Set();
                const results = [];

                const groupSelectors = [
                    '.fb-dash-form-element',
                    '.jobs-easy-apply-form-element',
                    '.artdeco-form-element',
                    '[data-test-form-element]',
                    'fieldset',
                ];

                for (const groupSelector of groupSelectors) {
                    for (const group of container.querySelectorAll(groupSelector)) {
                        const input = group.querySelector(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), ' +
                            'select, textarea'
                        );
                        if (!input || seen.has(input)) continue;

                        const style = window.getComputedStyle(input);
                        if (style.display === 'none' && input.type !== 'file') continue;
                        if (style.visibility === 'hidden' && input.type !== 'file') continue;

                        seen.add(input);
                        let labelText = getGroupLabel(group, input);

                        if (!labelText && input.id) {
                            const label = container.querySelector(`label[for="${input.id}"]`);
                            if (label) labelText = label.textContent.trim();
                        }
                        if (!labelText && input.getAttribute('aria-label')) {
                            labelText = input.getAttribute('aria-label');
                        }
                        if (!labelText && input.getAttribute('aria-labelledby')) {
                            const labelEl = document.getElementById(
                                input.getAttribute('aria-labelledby')
                            );
                            if (labelEl) labelText = labelEl.textContent.trim();
                        }

                        let options = [];
                        if (input.tagName === 'SELECT') {
                            options = Array.from(input.options)
                                .map((o) => o.text.trim())
                                .filter((t) => t);
                        }

                        const isRequired = input.required ||
                            input.getAttribute('aria-required') === 'true' ||
                            group.getAttribute('aria-required') === 'true' ||
                            (labelText && labelText.includes('*')) ||
                            !!group.querySelector('[aria-required="true"], .artdeco-form-element--required');

                        let fieldType = input.type || input.tagName.toLowerCase();
                        if (input.getAttribute('role') === 'combobox') {
                            fieldType = 'combobox';
                        } else if (input.inputMode === 'numeric' || input.type === 'number') {
                            fieldType = 'number';
                        }

                        results.push({
                            selector: buildSelector(input),
                            fieldType,
                            labelText: labelText || null,
                            nameAttr: input.name || null,
                            idAttr: input.id || null,
                            placeholder: input.placeholder || null,
                            isRequired,
                            currentValue: input.value || null,
                            options,
                            ariaRole: input.getAttribute('role') || null,
                        });
                    }
                }

                const elements = container.querySelectorAll(
                    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), ' +
                    'select, textarea'
                );
                for (const el of elements) {
                    if (seen.has(el)) continue;

                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' && el.type !== 'file') continue;
                    if (style.visibility === 'hidden' && el.type !== 'file') continue;

                    let labelText = '';
                    if (el.id) {
                        const label = container.querySelector(`label[for="${el.id}"]`);
                        if (label) labelText = label.textContent.trim();
                    }
                    if (!labelText && el.getAttribute('aria-label')) {
                        labelText = el.getAttribute('aria-label');
                    }
                    if (!labelText) {
                        labelText = getGroupLabel(el.closest('.artdeco-form-element, fieldset'), el);
                    }

                    let options = [];
                    if (el.tagName === 'SELECT') {
                        options = Array.from(el.options).map((o) => o.text.trim()).filter((t) => t);
                    }

                    const isRequired = el.required ||
                        el.getAttribute('aria-required') === 'true' ||
                        (labelText && labelText.includes('*'));

                    let fieldType = el.type || el.tagName.toLowerCase();
                    if (el.getAttribute('role') === 'combobox') {
                        fieldType = 'combobox';
                    }

                    results.push({
                        selector: buildSelector(el),
                        fieldType,
                        labelText: labelText || null,
                        nameAttr: el.name || null,
                        idAttr: el.id || null,
                        placeholder: el.placeholder || null,
                        isRequired,
                        currentValue: el.value || null,
                        options,
                        ariaRole: el.getAttribute('role') || null,
                    });
                }
                return results;
            }
            """,
            container_selector,
        )

        for raw in raw_fields:
            f = DetectedField(
                selector=raw["selector"],
                field_type=raw["fieldType"],
                label_text=raw["labelText"],
                name_attr=raw["nameAttr"],
                id_attr=raw["idAttr"],
                placeholder=raw["placeholder"],
                is_required=raw["isRequired"],
                current_value=raw["currentValue"],
                options=raw["options"],
                aria_role=raw.get("ariaRole"),
            )
            fields.append(f)

        logger.debug(
            "Detected %d form fields in '%s'", len(fields), container_selector
        )
        for f in fields:
            logger.debug(
                "  Field: type=%s label=%r name=%r required=%s",
                f.field_type,
                f.label_text,
                f.name_attr,
                f.is_required,
            )

        return fields

    async def detect_radio_groups(
        self, page: Page, container_selector: str = "body"
    ) -> dict[str, list[dict]]:
        """Detect radio button groups within a container.

        Returns a dict mapping group name to list of {value, label, selector}.
        """
        groups = await page.evaluate(
            """
            (containerSelector) => {
                const container = document.querySelector(containerSelector) || document.body;
                const radios = container.querySelectorAll('input[type="radio"]');
                const groups = {};

                for (const radio of radios) {
                    const name = radio.name;
                    if (!name) continue;
                    if (!groups[name]) groups[name] = [];

                    let label = '';
                    if (radio.id) {
                        const labelEl = container.querySelector(`label[for="${radio.id}"]`);
                        if (labelEl) label = labelEl.textContent.trim();
                    }
                    if (!label) {
                        const parentLabel = radio.closest('label');
                        if (parentLabel) label = parentLabel.textContent.trim();
                    }

                    groups[name].push({
                        value: radio.value,
                        label: label || radio.value,
                        selector: radio.id ? '#' + CSS.escape(radio.id) :
                            `input[name="${name}"][value="${radio.value}"]`,
                    });
                }
                return groups;
            }
            """,
            container_selector,
        )
        return groups
