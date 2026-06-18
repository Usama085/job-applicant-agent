"""Open a browser for manual login to save session cookies.

Usage:
    python scripts/manual_login.py linkedin
    python scripts/manual_login.py indeed

The script opens a persistent browser context (headed mode).
Log in manually. When done, press Enter in the terminal.
The browser state (cookies, localStorage) is saved automatically.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_agent.config import Settings


PLATFORM_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "indeed": "https://secure.indeed.com/auth",
}


async def manual_login(platform: str) -> None:
    from playwright.async_api import async_playwright

    settings = Settings.from_env()
    user_data_dir = settings.browser_data_dir / platform
    user_data_dir.mkdir(parents=True, exist_ok=True)

    url = PLATFORM_URLS.get(platform)
    if not url:
        print(f"Unknown platform: {platform}")
        print(f"Supported: {', '.join(PLATFORM_URLS)}")
        return

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport={"width": 1366, "height": 768},
            locale="en-PK",
            timezone_id="Asia/Karachi",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url)

        print(f"\n{'='*50}")
        print(f"  Browser opened for: {platform.upper()}")
        print(f"{'='*50}")
        print(f"  URL: {url}")
        print()
        print("  1. Log in to your account in the browser")
        print("  2. Make sure you are fully logged in")
        print("  3. Come back here and press ENTER to save the session")
        print(f"\n{'='*50}")

        # Wait for user input (run in executor to not block async loop)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "\nPress ENTER after logging in... ")

        await context.close()
        print(f"\nSession saved to: {user_data_dir}")
        print("You can now run the agent and it will use this session.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/manual_login.py <platform>")
        print(f"Platforms: {', '.join(PLATFORM_URLS)}")
        sys.exit(1)

    platform = sys.argv[1].lower()
    asyncio.run(manual_login(platform))


if __name__ == "__main__":
    main()
