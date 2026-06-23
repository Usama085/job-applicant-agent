"""Indeed platform implementation -- ties together search and apply."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from job_agent.platforms.base import BasePlatform, SearchQuery, SearchResult
from job_agent.platforms.indeed import constants
from job_agent.platforms.indeed.applier import IndeedApplier
from job_agent.platforms.indeed.searcher import IndeedSearcher

if TYPE_CHECKING:
    from job_agent.database.models import Application, Job

logger = logging.getLogger("job_agent.platforms.indeed.platform")


class IndeedPlatform(BasePlatform):
    """Indeed platform: search and apply to jobs via browser automation."""

    @property
    def platform_name(self) -> str:
        return "indeed"

    async def is_logged_in(self) -> bool:
        """Check if Indeed session is valid."""
        page = await self.session.get_page()

        try:
            await page.goto(constants.HOME_URL, wait_until="domcontentloaded")
            await self.humanizer.random_delay()

            logged_in = await page.locator(constants.LOGGED_IN_SELECTOR).count()
            if logged_in > 0:
                logger.info("Indeed: logged in successfully")
                return True

            if "/auth" in page.url or "/login" in page.url:
                logger.warning("Indeed: session expired (redirected to login)")
                return False

            cookies = await self.session.context.cookies()
            auth_cookie_names = {
                "CTK",
                "PPID",
                "SHOE",
                "SOCK",
                "INDEED_CSRF_TOKEN",
                "LV",
            }
            if any(
                cookie.get("name") in auth_cookie_names and cookie.get("value")
                for cookie in cookies
            ):
                logger.info("Indeed: logged in (session cookie present)")
                return True

            account_menu = await page.locator(
                '[data-gnav-element-name="AccountMenu"], '
                'button[aria-label*="Account"], '
                'a[aria-label*="Account"]'
            ).count()
            if account_menu > 0:
                logger.info("Indeed: logged in (account menu visible)")
                return True

            logger.warning("Indeed: not logged in — run: python scripts/manual_login.py indeed")
            return False

        except Exception as e:
            logger.error("Indeed: login check failed: %s", e)
            return False

    async def search_jobs(self, query: SearchQuery) -> SearchResult:
        """Search Indeed for jobs matching the query."""
        page = await self.session.get_page()
        searcher = IndeedSearcher(page, self.humanizer)
        return await searcher.search(query)

    async def get_job_description(self, job: Job) -> str:
        """Load the visible Indeed job page text for local matching."""
        page = await self.session.get_page()
        await page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()
        try:
            return await page.inner_text("body")
        except Exception:
            return ""

    async def apply_to_job(self, job: Job) -> Application:
        """Apply to a single Indeed job."""
        page = await self.session.get_page()
        applier = IndeedApplier(
            page=page,
            humanizer=self.humanizer,
            form_detector=self.form_detector,
            form_filler=self.form_filler,
            resume_uploader=self.resume_uploader,
            captcha_detector=self.captcha_detector,
        )
        return await applier.apply(job)
