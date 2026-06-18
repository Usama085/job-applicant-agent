"""Playwright-stealth wrapper for anti-detection measures."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

logger = logging.getLogger("job_agent.browser.stealth")


async def apply_stealth(context: BrowserContext) -> None:
    """Apply stealth evasions to a Playwright browser context.

    Uses playwright-stealth v2 to patch common bot detection vectors:
    - navigator.webdriver
    - User-Agent (removes HeadlessChrome)
    - navigator.plugins
    - navigator.languages
    - WebGL renderer
    - chrome.runtime
    - iframe.contentWindow
    """
    try:
        from playwright_stealth import Stealth

        stealth = Stealth()
        await stealth.apply_stealth_async(context)
        logger.info("Stealth evasions applied successfully")
    except ImportError:
        logger.warning(
            "playwright-stealth not installed. Running without stealth evasions. "
            "Install with: pip install playwright-stealth"
        )
    except Exception as e:
        logger.warning("Failed to apply stealth evasions: %s", e)
