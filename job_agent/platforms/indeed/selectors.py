"""Indeed CSS/XPath selectors -- centralized for easy maintenance.

Last verified: 2026-02-17
Indeed updates their DOM regularly. Update selectors here when automation breaks.
"""

# === Job Search Page ===

# Job card in search results
JOB_CARD = ".job_seen_beacon, .resultContent, .slider_item"

# Job title link
JOB_TITLE_LINK = ".jcs-JobTitle, h2.jobTitle a, a[data-jk]"

# Company name
JOB_COMPANY = "[data-testid='company-name'], .companyName, .company"

# Location
JOB_LOCATION = "[data-testid='text-location'], .companyLocation, .location"

# Search results container
RESULTS_LIST = "#mosaic-jobResults, .jobsearch-ResultsList, #resultsCol"

# No results indicator
NO_RESULTS = ".jobsearch-NoResult-messageContainer"

# Pagination next
PAGINATION_NEXT = 'a[data-testid="pagination-page-next"], a[aria-label="Next Page"]'

# Job card link (to get job ID / URL)
JOB_LINK = "a[data-jk], .jcs-JobTitle"

# === Job Detail Page ===

# Apply button (Indeed's own apply flow)
APPLY_BUTTON = (
    '#indeedApplyButton, '
    'button[id="indeedApplyButton"], '
    '.jobsearch-IndeedApplyButton-newDesign, '
    'button.indeedApplyButtonContainer'
)

# External apply button
EXTERNAL_APPLY_BUTTON = (
    '.jobsearch-IndeedApplyButton-newDesign a[href], '
    'a[data-tn-element="apply-button"]'
)

# "Easily apply" badge
EASILY_APPLY_BADGE = ".jobCardShelfContainer .iaLabel, .indeed-apply-badge"

# === Indeed Apply Flow ===

# Apply modal/iframe
APPLY_MODAL = '#indeed-ia-modal, iframe[title*="Apply"]'
APPLY_IFRAME = 'iframe[id*="indeedapply"], iframe[title*="Apply"]'

# Form fields within apply flow
APPLY_FORM = '#ia-container form, .ia-Questions'

# Continue / Next button in apply flow
CONTINUE_BUTTON = (
    'button[id="ia-continue"], '
    'button:has-text("Continue"), '
    'button:has-text("Next"), '
    '.ia-continueButton'
)

# Submit button in apply flow
SUBMIT_BUTTON = (
    'button[id="ia-submit"], '
    'button:has-text("Submit your application"), '
    'button:has-text("Submit"), '
    '.ia-submitButton'
)

# Application success
APPLICATION_SUCCESS = (
    '.ia-PostApply-header, '
    'h1:has-text("Application submitted"), '
    'div:has-text("Your application has been submitted")'
)

# Resume upload in apply flow
FILE_INPUT = 'input[type="file"], #ia-file-upload'

# Error messages
FORM_ERROR = ".ia-Questions-errorMessage, .ia-error"

# === Login ===
EMAIL_INPUT = "#ifl-InputFormField-3, #login-email-input"
PASSWORD_INPUT = "#ifl-InputFormField-7, #login-password-input"
LOGIN_SUBMIT = 'button[type="submit"]'
