"""LinkedIn-specific URLs, limits, and configuration."""

# Base URLs
LOGIN_URL = "https://www.linkedin.com/login"
FEED_URL = "https://www.linkedin.com/feed/"
JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search/"

# Search URL parameters
SEARCH_PARAMS = {
    "keywords": "",          # Job title
    "location": "",          # Location
    "f_TPR": "r86400",      # Time posted: past 24 hours
    "f_E": "2",             # Experience level: Entry (1), Associate (2)
    "sortBy": "DD",         # Sort by date
    "f_AL": "",             # Easy Apply filter: "true" or ""
    "start": "0",           # Pagination offset
}

# Experience level filter values
EXPERIENCE_LEVELS = {
    1: "1",    # Internship
    2: "2",    # Entry level
    3: "2,3",  # Entry + Associate
    5: "2,3,4",  # Entry + Associate + Mid-Senior
}

# Timeouts
PAGE_LOAD_TIMEOUT_MS = 20000
MODAL_TIMEOUT_MS = 10000
ELEMENT_TIMEOUT_MS = 10000
APPLY_BUTTON_WAIT_MS = 12000

# Pagination
MAX_SEARCH_PAGES = 5
JOBS_PER_PAGE = 25

# Logged-in indicators (LinkedIn changes these often — keep multiple fallbacks)
LOGGED_IN_SELECTOR = (
    ".global-nav__me-photo, "
    ".feed-identity-module, "
    "button.global-nav__primary-link--me, "
    "img.global-nav__me-photo, "
    "[data-test-global-nav-me], "
    ".global-nav__me-content, "
    ".feed-shared-update-v2"
)
