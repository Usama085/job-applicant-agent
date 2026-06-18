"""CAPTCHA, OTP, and security challenge detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("job_agent.captcha.detector")


@dataclass
class CaptchaSignal:
    """Information about a detected CAPTCHA or security challenge."""

    captcha_type: str  # recaptcha, hcaptcha, cloudflare, otp, security_check
    element_selector: str | None
    page_url: str


# CSS selectors that indicate CAPTCHA presence
CAPTCHA_SELECTORS: dict[str, list[str]] = {
    "recaptcha": [
        'iframe[src*="recaptcha"]',
        "#g-recaptcha",
        ".g-recaptcha",
        'iframe[title*="reCAPTCHA"]',
    ],
    "hcaptcha": [
        'iframe[src*="hcaptcha"]',
        ".h-captcha",
        "#hcaptcha",
    ],
    "cloudflare": [
        "#challenge-form",
        'iframe[src*="challenges.cloudflare.com"]',
        "#cf-challenge-running",
        ".cf-browser-verification",
    ],
    "otp": [
        'input[name*="verification"]',
        'input[name*="otp"]',
        'input[aria-label*="verification code"]',
        'input[name*="pin"]',
        'input[autocomplete="one-time-code"]',
    ],
}

# Text patterns that indicate security challenges
SECURITY_TEXT_PATTERNS: list[str] = [
    "verify you are human",
    "verify you're human",
    "security check",
    "unusual activity",
    "confirm you are not a robot",
    "please verify",
    "identity verification",
    "let's do a quick security check",
    "we need to verify",
    "challenge-platform",
]


class CaptchaDetector:
    """Detects CAPTCHA, OTP, and security challenges on pages."""

    async def check(self, page: Page) -> CaptchaSignal | None:
        """Check the current page for CAPTCHA or security challenges.

        Returns a CaptchaSignal if detected, None if the page is clear.
        """
        url = page.url

        # Check CSS selectors for known CAPTCHA elements
        for captcha_type, selectors in CAPTCHA_SELECTORS.items():
            for selector in selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.warning(
                            "CAPTCHA detected: type=%s selector=%s url=%s",
                            captcha_type,
                            selector,
                            url,
                        )
                        return CaptchaSignal(
                            captcha_type=captcha_type,
                            element_selector=selector,
                            page_url=url,
                        )
                except Exception:
                    continue

        # Check page text for security challenge phrases
        try:
            body_text = await page.inner_text("body")
            body_lower = body_text.lower()

            for pattern in SECURITY_TEXT_PATTERNS:
                if pattern in body_lower:
                    logger.warning(
                        "Security challenge text detected: '%s' at %s",
                        pattern,
                        url,
                    )
                    return CaptchaSignal(
                        captcha_type="security_check",
                        element_selector=None,
                        page_url=url,
                    )
        except Exception:
            pass

        return None
