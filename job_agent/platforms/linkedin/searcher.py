"""LinkedIn job search -- navigates search pages and extracts job listings."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from job_agent.database.models import Job
from job_agent.platforms.base import SearchQuery, SearchResult
from job_agent.platforms.linkedin import constants, selectors

if TYPE_CHECKING:
    from playwright.async_api import Page

    from job_agent.browser.humanizer import HumanBehavior

logger = logging.getLogger("job_agent.platforms.linkedin.searcher")


class LinkedInSearcher:
    """Handles LinkedIn job search page navigation and job card extraction."""

    def __init__(self, page: Page, humanizer: HumanBehavior):
        self.page = page
        self.humanizer = humanizer

    async def search(
        self, query: SearchQuery, max_pages: int = constants.MAX_SEARCH_PAGES
    ) -> SearchResult:
        """Search LinkedIn for jobs matching the query.

        Navigates to the search page, extracts job cards from multiple pages,
        and returns deduplicated results.
        """
        all_jobs: list[Job] = []
        pages_searched = 0

        for page_num in range(max_pages):
            url = self._build_search_url(query, page_num)
            logger.info("Searching page %d: %s", page_num + 1, url)

            await self.page.goto(url, wait_until="domcontentloaded")
            await self.humanizer.random_delay()

            # Wait for results to load
            try:
                await self.page.wait_for_selector(
                    selectors.RESULTS_LIST,
                    timeout=constants.PAGE_LOAD_TIMEOUT_MS,
                )
            except Exception:
                # Check if no results
                no_results = await self.page.locator(selectors.NO_RESULTS).count()
                if no_results > 0:
                    logger.info("No results found for this query")
                    break
                logger.warning("Results list not found on page %d", page_num + 1)
                break

            await self.humanizer.simulate_reading(self.page)

            # Extract job cards
            jobs = await self._extract_job_cards()
            if not jobs:
                logger.info("No more jobs found on page %d", page_num + 1)
                break

            all_jobs.extend(jobs)
            pages_searched += 1

            # Check if there's a next page
            has_next = await self._has_next_page()
            if not has_next:
                break

            await self.humanizer.random_delay()

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_jobs: list[Job] = []
        for job in all_jobs:
            if job.job_url not in seen_urls:
                seen_urls.add(job.job_url)
                unique_jobs.append(job)

        logger.info(
            "Search complete: %d unique jobs from %d pages",
            len(unique_jobs),
            pages_searched,
        )

        return SearchResult(
            jobs=unique_jobs,
            total_found=len(unique_jobs),
            pages_searched=pages_searched,
        )

    def _build_search_url(self, query: SearchQuery, page_num: int = 0) -> str:
        """Construct the LinkedIn job search URL with filters."""
        # Determine experience level filter
        exp_filter = constants.EXPERIENCE_LEVELS.get(
            query.experience_max_years,
            constants.EXPERIENCE_LEVELS[3],  # Default: Entry + Associate
        )

        params = {
            "keywords": query.title,
            "location": query.location,
            "f_TPR": "r86400",  # Past 24 hours
            "f_E": exp_filter,
            "f_AL": "true",     # Easy Apply only
            "sortBy": "DD",     # Sort by date
            "start": str(page_num * constants.JOBS_PER_PAGE),
        }

        return f"{constants.JOBS_SEARCH_URL}?{urlencode(params)}"

    async def _extract_job_cards(self) -> list[Job]:
        """Extract job data from all visible job cards on the current page."""
        jobs: list[Job] = []

        cards = await self.page.evaluate(
            """
            () => {
                const cards = document.querySelectorAll(
                    '.job-card-container, .jobs-search-results__list-item, ' +
                    '.scaffold-layout__list-item'
                );
                const results = [];

                for (const card of cards) {
                    // Title and link
                    const titleLink = card.querySelector(
                        '.job-card-list__title, ' +
                        '.job-card-container__link, ' +
                        'a[data-control-name="job_card_title"],' +
                        'a.job-card-list__title--link'
                    );
                    if (!titleLink) continue;

                    const title = titleLink.textContent.trim();
                    let url = titleLink.href || '';

                    // Clean up URL (remove tracking params)
                    if (url) {
                        try {
                            const u = new URL(url);
                            // Keep only the path up to /jobs/view/XXXXX
                            const match = u.pathname.match(/\\/jobs\\/view\\/\\d+/);
                            if (match) {
                                url = 'https://www.linkedin.com' + match[0];
                            }
                        } catch(e) {}
                    }

                    // Company
                    const companyEl = card.querySelector(
                        '.job-card-container__primary-description, ' +
                        '.artdeco-entity-lockup__subtitle, ' +
                        '.job-card-container__company-name'
                    );
                    const company = companyEl ? companyEl.textContent.trim() : '';

                    // Location
                    const locationEl = card.querySelector(
                        '.job-card-container__metadata-item, ' +
                        '.artdeco-entity-lockup__caption, ' +
                        '.job-card-container__metadata-wrapper'
                    );
                    const location = locationEl ? locationEl.textContent.trim() : '';

                    // Easy Apply badge
                    const easyApplyBadge = card.querySelector(
                        '.job-card-container__apply-method, ' +
                        '[data-test-job-easy-apply-badge]'
                    );
                    const isEasyApply = easyApplyBadge !== null &&
                        easyApplyBadge.textContent.toLowerCase().includes('easy apply');

                    if (title && url) {
                        results.push({
                            title,
                            url,
                            company,
                            location,
                            isEasyApply,
                        });
                    }
                }
                return results;
            }
            """
        )

        for card in cards:
            job = Job(
                platform="linkedin",
                title=card["title"],
                job_url=card["url"],
                company=card["company"] or None,
                location=card["location"] or None,
                is_easy_apply=card["isEasyApply"],
                is_external=not card["isEasyApply"],
                discovered_at=datetime.now(),
            )
            jobs.append(job)

        logger.debug("Extracted %d job cards from current page", len(jobs))
        return jobs

    async def _has_next_page(self) -> bool:
        """Check if there's a next page button available."""
        try:
            next_btn = self.page.locator(selectors.PAGINATION_NEXT)
            count = await next_btn.count()
            if count > 0:
                is_disabled = await next_btn.first.is_disabled()
                return not is_disabled
        except Exception:
            pass
        return False
