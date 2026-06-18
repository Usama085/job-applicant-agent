"""Human-like behavior simulation for browser automation."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("job_agent.browser.humanizer")


class HumanBehavior:
    """Injects human-like delays and interactions into browser automation."""

    def __init__(self, min_delay_ms: int = 800, max_delay_ms: int = 2500):
        self.min_delay = min_delay_ms / 1000.0
        self.max_delay = max_delay_ms / 1000.0

    async def random_delay(self) -> None:
        """Sleep for a random duration between min and max delay."""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def micro_pause(self) -> None:
        """Very short pause (100-400ms) between rapid sequential actions."""
        await asyncio.sleep(random.uniform(0.1, 0.4))

    async def think_pause(self) -> None:
        """Longer pause (2-5s) simulating reading or thinking."""
        await asyncio.sleep(random.uniform(2.0, 5.0))

    async def human_type(self, page: Page, selector: str, text: str) -> None:
        """Type text character-by-character with random inter-key delays.

        Clears existing value first, then types with 50-150ms per character,
        with occasional 200-400ms 'thinking' pauses.
        """
        element = page.locator(selector)
        await element.click()
        await self.micro_pause()

        # Clear existing value
        await element.fill("")
        await self.micro_pause()

        for i, char in enumerate(text):
            await element.press_sequentially(char, delay=0)
            # Base delay: 50-150ms per character
            delay = random.gauss(0.1, 0.03)
            delay = max(0.05, min(0.15, delay))

            # Occasional longer pause (every 5-12 characters)
            if i > 0 and random.random() < 0.1:
                delay += random.uniform(0.2, 0.4)

            await asyncio.sleep(delay)

    async def human_click(self, page: Page, selector: str) -> None:
        """Click an element with slight random offset from center."""
        element = page.locator(selector)
        box = await element.bounding_box()
        if box:
            # Random offset within element bounds (+-25% of dimensions)
            offset_x = random.uniform(-box["width"] * 0.25, box["width"] * 0.25)
            offset_y = random.uniform(-box["height"] * 0.25, box["height"] * 0.25)
            await element.click(
                position={
                    "x": box["width"] / 2 + offset_x,
                    "y": box["height"] / 2 + offset_y,
                }
            )
        else:
            await element.click()
        await self.micro_pause()

    async def random_scroll(self, page: Page) -> None:
        """Scroll page by a random amount to simulate reading."""
        scroll_amount = random.randint(200, 600)
        direction = 1 if random.random() > 0.15 else -1  # 85% down, 15% up
        await page.mouse.wheel(0, scroll_amount * direction)
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def simulate_reading(self, page: Page) -> None:
        """Simulate a user reading a page -- scroll and pause."""
        scrolls = random.randint(1, 3)
        for _ in range(scrolls):
            await self.random_scroll(page)
            await asyncio.sleep(random.uniform(0.8, 2.0))
