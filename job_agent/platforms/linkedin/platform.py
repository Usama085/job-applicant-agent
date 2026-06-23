"""LinkedIn platform implementation -- ties together search and apply."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from job_agent.platforms.base import BasePlatform, SearchQuery, SearchResult
from job_agent.platforms.linkedin import constants
from job_agent.platforms.linkedin.applier import LinkedInApplier
from job_agent.platforms.linkedin.searcher import LinkedInSearcher

if TYPE_CHECKING:
    from job_agent.database.models import Application, Job

logger = logging.getLogger("job_agent.platforms.linkedin.platform")


class LinkedInPlatform(BasePlatform):
    """LinkedIn platform: search and apply to jobs via browser automation."""

    @property
    def platform_name(self) -> str:
        return "linkedin"

    async def is_logged_in(self) -> bool:
        """Check if LinkedIn session is valid by looking for logged-in indicators."""
        page = await self.session.get_page()

        try:
            await page.goto(constants.FEED_URL, wait_until="domcontentloaded")
            await self.humanizer.random_delay()

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            for selector in constants.LOGGED_IN_SELECTOR.split(", "):
                if await page.locator(selector.strip()).count() > 0:
                    logger.info("LinkedIn: logged in successfully")
                    return True

            if any(
                marker in page.url
                for marker in ("/login", "/authwall", "/checkpoint", "/uas/login")
            ):
                logger.warning("LinkedIn: session expired (redirected to login)")
                return False

            cookies = await self.session.context.cookies("https://www.linkedin.com")
            if any(cookie.get("name") == "li_at" and cookie.get("value") for cookie in cookies):
                logger.info("LinkedIn: logged in (li_at session cookie present)")
                return True

            if "/feed" in page.url or page.url.rstrip("/").endswith("linkedin.com"):
                logger.info("LinkedIn: assuming logged in (active session at %s)", page.url)
                return True

            logger.warning("LinkedIn: login status unclear at %s", page.url)
            return False

        except Exception as e:
            logger.error("LinkedIn: login check failed: %s", e)
            return False

    async def search_jobs(self, query: SearchQuery) -> SearchResult:
        """Search LinkedIn for jobs matching the query."""
        page = await self.session.get_page()
        searcher = LinkedInSearcher(page, self.humanizer)
        return await searcher.search(query)

    async def get_job_description(self, job: Job) -> str:
        """Load the visible LinkedIn job page text for local matching."""
        page = await self.session.get_page()
        await page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()
        try:
            return await page.inner_text("body")
        except Exception:
            return ""

    async def apply_to_job(self, job: Job) -> Application:
        """Apply to a single LinkedIn job."""
        page = await self.session.get_page()
        applier = LinkedInApplier(
            page=page,
            humanizer=self.humanizer,
            form_detector=self.form_detector,
            form_filler=self.form_filler,
            resume_uploader=self.resume_uploader,
            captcha_detector=self.captcha_detector,
        )
        return await applier.apply(job)
