"""Browser session management with persistent context and stealth."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from job_agent.browser.stealth import apply_stealth
from job_agent.utils.exceptions import BrowserSessionError

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright

    from job_agent.config import Settings

logger = logging.getLogger("job_agent.browser.session")


class BrowserSession:
    """Manages a Playwright persistent browser context for a single platform."""

    def __init__(self, platform: str, settings: Settings):
        self.platform = platform
        self.settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> Page:
        """Launch browser with persistent context and stealth.

        Returns the active page instance.
        """
        from playwright.async_api import async_playwright

        user_data_dir = self.settings.browser_data_dir / self.platform
        user_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Launching browser for %s (headless=%s, user_data=%s)",
            self.platform,
            self.settings.browser_headless,
            user_data_dir,
        )

        self._playwright = await async_playwright().start()

        try:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.settings.browser_headless,
                slow_mo=self.settings.browser_slow_mo,
                viewport={"width": 1366, "height": 768},
                locale="en-PK",
                timezone_id="Asia/Karachi",
                geolocation={"latitude": 31.5204, "longitude": 74.3587},
                permissions=["geolocation"],
                color_scheme="light",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars",
                ],
                ignore_default_args=["--enable-automation"],
            )
        except Exception as e:
            if self._playwright:
                await self._playwright.stop()
            raise BrowserSessionError(f"Failed to launch browser: {e}") from e

        # Apply stealth evasions
        await apply_stealth(self._context)

        # Set default timeout
        self._context.set_default_timeout(self.settings.browser_timeout_ms)

        # Get or create the active page
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        logger.info("Browser session started for %s", self.platform)
        return self._page

    async def stop(self) -> None:
        """Close the browser context and Playwright instance."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None
        except Exception as e:
            logger.warning("Error closing browser context: %s", e)

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.warning("Error stopping Playwright: %s", e)

        logger.info("Browser session stopped for %s", self.platform)

    async def get_page(self) -> Page:
        """Return current page, creating one if needed."""
        if self._page is None or self._page.is_closed():
            if self._context is None:
                raise BrowserSessionError("Browser context not started")
            self._page = await self._context.new_page()
        return self._page

    async def take_screenshot(self, name: str) -> Path:
        """Save a screenshot for debugging. Returns the file path."""
        screenshot_dir = self.settings.screenshot_dir
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.platform}_{name}_{timestamp}.png"
        filepath = screenshot_dir / filename

        page = await self.get_page()
        await page.screenshot(path=str(filepath), full_page=False)
        logger.info("Screenshot saved: %s", filepath)
        return filepath

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise BrowserSessionError("Browser context not started")
        return self._context
