"""LinkedIn CSS/XPath selectors -- centralized for easy maintenance.

Last verified: 2026-02-17
LinkedIn frequently updates their DOM. If automation breaks, update selectors here.
"""

# === Job Search Page ===

# Job card container in search results
JOB_CARD = ".job-card-container, .jobs-search-results__list-item"

# Job title link within a card
JOB_TITLE_LINK = ".job-card-list__title, .job-card-container__link"

# Company name within a card
JOB_COMPANY = ".job-card-container__primary-description, .artdeco-entity-lockup__subtitle"

# Location within a card
JOB_LOCATION = ".job-card-container__metadata-item, .artdeco-entity-lockup__caption"

# Easy Apply badge on job card
EASY_APPLY_BADGE = ".job-card-container__apply-method, [data-test-job-easy-apply-badge]"

# Pagination buttons
PAGINATION_NEXT = 'button[aria-label="View next page"], .artdeco-pagination__button--next'
PAGINATION_ITEMS = ".artdeco-pagination__pages li button"

# Search results list container
RESULTS_LIST = ".jobs-search-results-list, .scaffold-layout__list"

# No results indicator
NO_RESULTS = ".jobs-search-no-results-banner, .jobs-search-two-pane__no-results"

# === Job Detail Page ===

# Job detail panel (right side or full page)
JOB_DETAIL_PANEL = ".job-view-layout, .jobs-unified-top-card"

# Job title on detail page
JOB_DETAIL_TITLE = ".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title"

# Company name on detail page
JOB_DETAIL_COMPANY = ".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name"

# Easy Apply button (LinkedIn 2025+ uses <a> with aria-label, not button.jobs-apply-button)
EASY_APPLY_BUTTON = (
    'a[aria-label*="Easy Apply"], '
    'button[aria-label*="Easy Apply"], '
    'button.jobs-apply-button[aria-label*="Easy Apply"], '
    'button[data-control-name="jobdetails_topcard_inapply"], '
    '.jobs-apply-button--top-card button:has-text("Easy Apply"), '
    'button:has-text("Easy Apply"), '
    'a:has-text("Easy Apply"), '
    '#jobs-apply-button-id'
)

# Any apply control on the job page (Easy Apply or external)
APPLY_BUTTON = (
    'a[aria-label*="Easy Apply"], '
    'a[aria-label*="Apply on company"], '
    'a[aria-label*="Apply"], '
    'button[aria-label*="Easy Apply"], '
    'button[aria-label*="Apply"], '
    'button.jobs-apply-button, '
    'a.jobs-apply-button, '
    '.jobs-apply-button--top-card a, '
    '.jobs-apply-button--top-card button, '
    '#jobs-apply-button-id'
)

# External Apply button
EXTERNAL_APPLY_BUTTON = (
    'a[aria-label*="Apply on company"], '
    'a[aria-label*="Apply"]:not([aria-label*="Easy Apply"]), '
    'button.jobs-apply-button:not([aria-label*="Easy Apply"]), '
    'a.jobs-apply-button, '
    'a:has-text("Apply"):not(:has-text("Easy Apply"))'
)

# === Easy Apply Modal ===

# Modal container
MODAL = ".jobs-easy-apply-modal, .artdeco-modal"

# Modal content area (form fields are inside this)
MODAL_CONTENT = ".jobs-easy-apply-content, .artdeco-modal__content"

# Modal footer with action buttons
MODAL_FOOTER = ".jobs-easy-apply-footer, .artdeco-modal__actionbar"

# Next button in modal
MODAL_NEXT = (
    'button[aria-label="Continue to next step"], '
    'button[aria-label="Next"], '
    'footer button[data-easy-apply-next-button], '
    '.jobs-easy-apply-footer button.artdeco-button--primary:has-text("Next"), '
    '.artdeco-modal__actionbar button.artdeco-button--primary:has-text("Next"), '
    'button:has-text("Continue")'
)

# Review button in modal
MODAL_REVIEW = (
    'button[aria-label="Review your application"], '
    'button[aria-label="Review"], '
    'button:has-text("Review")'
)

# Submit button in modal
MODAL_SUBMIT = (
    'button[aria-label="Submit application"], '
    'button[aria-label="Submit"], '
    'footer button[data-easy-apply-submit-button], '
    '.jobs-easy-apply-footer button.artdeco-button--primary:has-text("Submit"), '
    '.artdeco-modal__actionbar button.artdeco-button--primary:has-text("Submit"), '
    'button:has-text("Submit application")'
)

# Dismiss/close button after submission
MODAL_DISMISS = (
    'button[aria-label="Dismiss"], '
    'button[aria-label="Done"], '
    '.artdeco-modal__dismiss'
)

# Success indicator after submission
APPLICATION_SUCCESS = (
    '.artdeco-inline-feedback--success, '
    '[data-test-artdeco-toast], '
    '.artdeco-toast-item--visible'
)

# File upload input within modal
MODAL_FILE_INPUT = '.jobs-easy-apply-modal input[type="file"]'

# Error/validation messages in modal
MODAL_ERROR = ".artdeco-inline-feedback--error, .fb-dash-form-element__error-field"

# === Login Page ===

USERNAME_INPUT = "#username"
PASSWORD_INPUT = "#password"
LOGIN_SUBMIT = 'button[type="submit"]'
