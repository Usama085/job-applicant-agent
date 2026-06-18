"""Indeed-specific URLs, limits, and configuration."""

# Base URLs (Pakistan Indeed)
LOGIN_URL = "https://secure.indeed.com/auth"
HOME_URL = "https://pk.indeed.com/"
JOBS_SEARCH_URL = "https://pk.indeed.com/jobs"

# Search URL parameters
# q = query, l = location, fromage = days posted, sort = date
SEARCH_PARAMS = {
    "q": "",           # Job title keywords
    "l": "",           # Location
    "fromage": "1",    # Posted within X days (1 = last 24 hours)
    "sort": "date",    # Sort by date
    "start": "0",      # Pagination offset (multiples of 10)
}

# Timeouts
PAGE_LOAD_TIMEOUT_MS = 15000
ELEMENT_TIMEOUT_MS = 5000
APPLY_TIMEOUT_MS = 10000

# Pagination
MAX_SEARCH_PAGES = 5
JOBS_PER_PAGE = 15  # Indeed typically shows 15 per page

# Logged-in indicator
LOGGED_IN_SELECTOR = '[data-gnav-element-name="AccountMenu"], .gnav-LoggedInAccountLink'
