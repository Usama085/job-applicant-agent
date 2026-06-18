"""Indeed job search -- navigates search pages and extracts job listings."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from job_agent.database.models import Job
from job_agent.platforms.base import SearchQuery, SearchResult
from job_agent.platforms.indeed import constants, selectors

if TYPE_CHECKING:
    from playwright.async_api import Page

    from job_agent.browser.humanizer import HumanBehavior

logger = logging.getLogger("job_agent.platforms.indeed.searcher")


class IndeedSearcher:
    """Handles Indeed job search page navigation and listing extraction."""

    def __init__(self, page: Page, humanizer: HumanBehavior):
        self.page = page
        self.humanizer = humanizer

    async def search(
        self, query: SearchQuery, max_pages: int = constants.MAX_SEARCH_PAGES
    ) -> SearchResult:
        """Search Indeed for jobs matching the query."""
        all_jobs: list[Job] = []
        pages_searched = 0

        for page_num in range(max_pages):
            url = self._build_search_url(query, page_num)
            logger.info("Searching Indeed page %d: %s", page_num + 1, url)

            await self.page.goto(url, wait_until="domcontentloaded")
            await self.humanizer.random_delay()

            # Wait for results
            try:
                await self.page.wait_for_selector(
                    selectors.RESULTS_LIST,
                    timeout=constants.PAGE_LOAD_TIMEOUT_MS,
                )
            except Exception:
                no_results = await self.page.locator(selectors.NO_RESULTS).count()
                if no_results > 0:
                    logger.info("Indeed: no results found")
                    break
                logger.warning("Indeed: results not found on page %d", page_num + 1)
                break

            await self.humanizer.simulate_reading(self.page)

            # Extract job cards
            jobs = await self._extract_job_cards()
            if not jobs:
                logger.info("Indeed: no more jobs on page %d", page_num + 1)
                break

            all_jobs.extend(jobs)
            pages_searched += 1

            # Check for next page
            has_next = await self._has_next_page()
            if not has_next:
                break

            await self.humanizer.random_delay()

        # Deduplicate
        seen_urls: set[str] = set()
        unique_jobs: list[Job] = []
        for job in all_jobs:
            if job.job_url not in seen_urls:
                seen_urls.add(job.job_url)
                unique_jobs.append(job)

        logger.info(
            "Indeed search complete: %d unique jobs from %d pages",
            len(unique_jobs),
            pages_searched,
        )

        return SearchResult(
            jobs=unique_jobs,
            total_found=len(unique_jobs),
            pages_searched=pages_searched,
        )

    def _build_search_url(self, query: SearchQuery, page_num: int = 0) -> str:
        """Construct Indeed search URL with filters."""
        params = {
            "q": query.title,
            "l": query.location,
            "fromage": "1",  # Last 24 hours
            "sort": "date",
            "start": str(page_num * constants.JOBS_PER_PAGE),
        }
        return f"{constants.JOBS_SEARCH_URL}?{urlencode(params)}"

    async def _extract_job_cards(self) -> list[Job]:
        """Extract job data from search result cards."""
        jobs: list[Job] = []

        cards = await self.page.evaluate(
            """
            () => {
                const cards = document.querySelectorAll(
                    '.job_seen_beacon, .resultContent, .slider_item, ' +
                    '.jobsearch-ResultsList .result'
                );
                const results = [];

                for (const card of cards) {
                    // Title and link
                    const titleEl = card.querySelector(
                        '.jcs-JobTitle, h2.jobTitle a, a[data-jk], ' +
                        'a.jcs-JobTitle'
                    );
                    if (!titleEl) continue;

                    const title = titleEl.textContent.trim();
                    let url = titleEl.href || '';

                    // Extract job key for constructing URL
                    const jk = titleEl.getAttribute('data-jk') ||
                               card.querySelector('[data-jk]')?.getAttribute('data-jk');
                    if (jk && !url) {
                        url = 'https://pk.indeed.com/viewjob?jk=' + jk;
                    }
                    if (url && !url.startsWith('http')) {
                        url = 'https://pk.indeed.com' + url;
                    }

                    // Company
                    const companyEl = card.querySelector(
                        '[data-testid="company-name"], .companyName, ' +
                        '.company, .companyInfo'
                    );
                    const company = companyEl ? companyEl.textContent.trim() : '';

                    // Location
                    const locationEl = card.querySelector(
                        '[data-testid="text-location"], .companyLocation, ' +
                        '.location, .locationAccessibility'
                    );
                    const location = locationEl ? locationEl.textContent.trim() : '';

                    // Easy apply badge
                    const easyApply = card.querySelector(
                        '.iaLabel, .indeed-apply-badge, .iaIcon'
                    ) !== null;

                    if (title && url) {
                        results.push({
                            title,
                            url,
                            company,
                            location,
                            easyApply,
                            jk: jk || '',
                        });
                    }
                }
                return results;
            }
            """
        )

        for card in cards:
            job = Job(
                platform="indeed",
                title=card["title"],
                job_url=card["url"],
                company=card["company"] or None,
                location=card["location"] or None,
                external_id=card.get("jk"),
                is_easy_apply=card["easyApply"],
                is_external=not card["easyApply"],
                discovered_at=datetime.now(),
            )
            jobs.append(job)

        logger.debug("Extracted %d job cards from Indeed page", len(jobs))
        return jobs

    async def _has_next_page(self) -> bool:
        """Check if there's a next page available."""
        try:
            next_btn = self.page.locator(selectors.PAGINATION_NEXT)
            return await next_btn.count() > 0
        except Exception:
            return False
