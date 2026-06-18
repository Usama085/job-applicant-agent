# AI Job Application Agent Details

Generated from source inspection on 2026-05-04.

This document explains what this codebase is, how it is organized, and what it does at runtime. The review intentionally excludes generated/runtime folders such as `venv/`, `__pycache__/`, and `.pytest_cache/`. It also avoids copying real `.env` values or personal profile values from `config/profile.yaml`.

## High-Level Summary

This is a Python 3.11 job application automation agent. It uses Playwright to control a Chromium browser, searches LinkedIn and Indeed for configured job queries, attempts to apply to matching jobs, records all discovered jobs and application attempts in SQLite, and sends email reports or urgent alerts through Gmail SMTP.

The package name is `job-agent`, and the main entrypoint is:

```bash
python -m job_agent.main
```

The project is described in `pyproject.toml` as:

> AI-powered job application automation agent for LinkedIn and Indeed

Important note: the current source does not call an LLM or external AI API. The "AI" behavior is mainly rule-based automation: browser automation, heuristic form detection, regex-based field mapping, human-like delays, anti-detection browser settings, and CAPTCHA/security-challenge detection.

## Main Technologies

- Python package: `job_agent`
- Browser automation: `playwright`
- Anti-detection wrapper: `playwright-stealth`
- Configuration: `.env` via `python-dotenv`, YAML via `pyyaml`
- Persistence: SQLite
- Email: Gmail SMTP with an app password
- Testing: `pytest` and `pytest-asyncio`
- Packaging/config: `pyproject.toml`, `requirements.txt`

## Runtime Flow

The main daily run starts in `job_agent/main.py`.

1. `Settings.from_env()` loads configuration from `.env` and environment variables.
2. `setup_logging()` configures a rotating file logger and console logger.
3. `load_profile()` loads applicant data from `config/profile.yaml`.
4. `load_search_queries()` loads job titles and locations from `config/search_queries.yaml`.
5. `ApplicationRepository` opens the SQLite database and creates tables if needed.
6. `EmailClient` and `DailyReporter` are initialized for reports and alerts.
7. Enabled platforms from `ENABLED_PLATFORMS` are shuffled to make runs less repetitive.
8. Each platform is processed through `run_platform()`.
9. After all platforms complete, the agent sends a daily summary email.
10. The database connection is closed and final run stats are logged.

For each platform, `run_platform()` creates shared services:

- `BrowserSession` for a persistent Playwright browser profile
- `HumanBehavior` for randomized waits, typing, scrolling, and click offsets
- `FormDetector` to discover form inputs on the page
- `FieldMapping` to match fields to profile values
- `FormFiller` to fill text inputs, textareas, selects, checkboxes, and radios
- `ResumeUploader` to upload the configured resume PDF
- `CaptchaDetector` and `CaptchaHandler`
- `RateLimiter`
- A platform implementation, currently either `LinkedInPlatform` or `IndeedPlatform`

Then it verifies login state, runs the platform search/apply cycle, updates the run log, catches login expiry or crashes, and always stops the browser session.

## Project Structure

```text
job_agent/
  main.py                  Main orchestration and CLI entrypoint
  config.py                Typed settings loaded from .env
  browser/                 Playwright session, stealth, human-like behavior
  captcha/                 CAPTCHA/security challenge detection and alert handling
  database/                SQLite models, schema, repository methods
  forms/                   Form detection, mapping, filling, resume upload
  notifications/           Gmail SMTP client and HTML report templates
  platforms/               Platform abstraction plus LinkedIn and Indeed support
  profile/                 User profile dataclasses and YAML loader
  utils/                   Logging, rate limiting, retry helpers, enums, exceptions

config/
  profile.yaml             Applicant profile data used for autofill
  search_queries.yaml      Job titles, locations, and search settings

scripts/
  manual_login.py          Opens browser so you can log in and save cookies
  reset_cookies.py         Clears saved browser session data
  run_agent.bat            Windows launcher for scheduled runs
  setup_scheduler.ps1      Creates a Windows scheduled task
  view_report.py           Reads the SQLite database and prints application reports

tests/
  test_config.py
  test_database/test_repository.py
  test_forms/test_field_mapping.py
```

Runtime data lives under `data/`:

- `data/browser_data/`: saved LinkedIn and Indeed browser sessions/cookies
- `data/db/`: SQLite database
- `data/logs/`: agent and scheduler logs
- `data/resumes/`: expected resume location
- `data/screenshots/`: failure/CAPTCHA screenshots

## Configuration

`job_agent/config.py` defines a frozen `Settings` dataclass. It reads values from `.env`, using defaults when variables are absent.

Key settings include:

- Browser: `BROWSER_HEADLESS`, `BROWSER_SLOW_MO`, `BROWSER_TIMEOUT_MS`, `BROWSER_DATA_DIR`
- Limits: `LINKEDIN_DAILY_LIMIT`, `INDEED_DAILY_LIMIT`
- Email: `SMTP_HOST`, `SMTP_PORT`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFICATION_RECIPIENT`
- Database: `DATABASE_PATH`
- Resume: `RESUME_PATH`
- Logging: `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
- Rate limiting: `RATE_LIMIT_LINKEDIN_RPM`, `RATE_LIMIT_INDEED_RPM`
- Human-like delays: `MIN_ACTION_DELAY_MS`, `MAX_ACTION_DELAY_MS`
- Retry settings: `MAX_RETRIES`, `RETRY_BACKOFF_BASE`, `RETRY_BACKOFF_MAX`
- Screenshots: `SCREENSHOT_DIR`, `SCREENSHOT_ON_FAILURE`
- Platforms: `ENABLED_PLATFORMS`

`config/search_queries.yaml` currently searches for:

- `DevOps Engineer`
- Location: `Lahore`
- Maximum experience filter: `3`
- Remote allowed: `true`

The same file also contains platform-specific search metadata for LinkedIn and Indeed, although the platform classes mostly use constants in code.

`config/profile.yaml` stores personal and professional application data. Its structure is:

- `personal`: name, email, phone, location, LinkedIn URL
- `professional`: title, company, years of experience, summary
- `application_defaults`: cover letter, salary, work authorization, sponsorship, availability, relocation, notice period
- `references`: optional reference contacts

## Browser Automation Layer

`job_agent/browser/session.py` owns the Playwright lifecycle.

It launches a persistent Chromium context per platform under:

```text
data/browser_data/<platform>
```

That means cookies and local storage survive between runs. The user logs in once with `scripts/manual_login.py`, and the agent reuses that stored session.

The browser context is configured with:

- Viewport: `1366x768`
- Locale: `en-PK`
- Timezone: `Asia/Karachi`
- Geolocation: Lahore coordinates
- `AutomationControlled` disabled
- `--enable-automation` ignored
- Default timeout from settings

`job_agent/browser/stealth.py` applies `playwright-stealth` to patch common bot-detection signals such as `navigator.webdriver`, headless user-agent hints, plugins, languages, WebGL, and related browser fingerprints.

`job_agent/browser/humanizer.py` provides:

- Random action delays
- Short micro-pauses
- Longer "thinking" pauses
- Character-by-character typing
- Clicks with random offsets
- Random scrolls and reading simulation

## Platform Abstraction

`job_agent/platforms/base.py` defines:

- `SearchQuery`: title, location, max experience, remote preference
- `SearchResult`: jobs, total found, pages searched
- `BasePlatform`: abstract methods for login check, search, and application

The shared `BasePlatform.run()` method handles the main platform workflow:

1. Check how many successful applications already happened today.
2. Stop early if the platform daily limit has already been reached.
3. Search all configured queries.
4. Randomize found jobs.
5. Randomly skip about 7 percent of jobs as an anti-pattern measure.
6. Save each job to SQLite.
7. Skip jobs that already have an `Applied` record.
8. Rate-limit before application attempts.
9. Call the platform-specific `apply_to_job()`.
10. Save the resulting application status.
11. Stop after 3 consecutive failures.
12. Handle CAPTCHA and form-filling errors with screenshots and records.

Application statuses are defined in `job_agent/utils/constants.py`:

- `Applied`
- `Failed`
- `Manual Intervention Required`
- `Skipped`
- `Duplicate`

## LinkedIn Support

LinkedIn code lives under `job_agent/platforms/linkedin/`.

`LinkedInPlatform` checks login by navigating to:

```text
https://www.linkedin.com/feed/
```

It looks for logged-in navigation elements and treats `/login` or `/authwall` redirects as expired sessions.

`LinkedInSearcher` builds search URLs for:

```text
https://www.linkedin.com/jobs/search/
```

It uses:

- `keywords`: configured job title
- `location`: configured location
- `f_TPR=r86400`: jobs from the past 24 hours
- `f_E`: LinkedIn experience-level filters
- `sortBy=DD`: sort by date
- `start`: pagination offset

It searches up to 5 pages, 25 jobs per page, extracts job cards with JavaScript, normalizes job URLs to `/jobs/view/<id>`, detects Easy Apply badges, and deduplicates by job URL.

`LinkedInApplier` handles two paths:

- Easy Apply: opens the modal, uploads resume if needed, detects/fills fields, advances through Next/Review/Submit, and records success/failure.
- External Apply: clicks the external apply button, handles a new tab or same-tab navigation, tries to detect and fill an external form, then attempts to submit.

LinkedIn selectors are centralized in `job_agent/platforms/linkedin/selectors.py`. The file notes they were last verified on 2026-02-17, which matters because LinkedIn changes DOM structures frequently.

## Indeed Support

Indeed code lives under `job_agent/platforms/indeed/`.

`IndeedPlatform` checks login by navigating to:

```text
https://pk.indeed.com/
```

It looks for account menu/login indicators. It returns false if a sign-in link is visible or if the browser is redirected to an auth/login URL.

`IndeedSearcher` builds search URLs for:

```text
https://pk.indeed.com/jobs
```

It uses:

- `q`: configured job title
- `l`: configured location
- `fromage=1`: jobs from the last day
- `sort=date`
- `start`: pagination offset

It searches up to 5 pages, about 15 jobs per page, extracts cards with JavaScript, builds job URLs from Indeed job keys where needed, detects Easy Apply style badges, and deduplicates by URL.

`IndeedApplier` handles:

- In-platform Indeed Apply
- Apply flows inside iframes
- Multi-step application pages
- External apply links

It uploads resumes, fills detected forms, clicks Continue/Next or Submit, and marks external forms as `Manual Intervention Required` if it can fill data but cannot confidently submit.

Indeed selectors are centralized in `job_agent/platforms/indeed/selectors.py`. That file also notes they were last verified on 2026-02-17.

## Form Detection and Filling

The form system is generic so it can work across LinkedIn, Indeed, and external career sites.

`FormDetector` scans a page or container for:

- `input` elements except hidden/submit/button inputs
- `select`
- `textarea`

For each field it collects:

- CSS selector
- Input type
- Label text
- `name`
- `id`
- Placeholder
- Required state
- Current value
- Select options

`DetectedField.identifiers` combines label/name/id/placeholder into a lowercase string. This string is passed to `FieldMapping`.

`FieldMapping` uses regex rules to map field identifiers to `UserProfile` attributes. It supports common fields like:

- First name
- Last name
- Full name
- Email
- Phone
- Location
- LinkedIn URL
- Years of experience
- Current title/company
- Summary
- Cover letter
- Salary expectation
- Work authorization
- Visa sponsorship
- Availability
- Notice period
- Relocation willingness

`FormFiller` fills matched fields using profile data. It supports:

- Text/email/tel/number/url/search inputs
- Textareas
- Select dropdowns with exact or fuzzy option matching
- Checkboxes
- Radio inputs

Cover letters can use placeholders:

```text
{company}
{title}
```

Those are replaced with the current job company and title.

`ResumeUploader` looks for `input[type='file']` fields and uploads the configured resume path, defaulting to:

```text
data/resumes/resume.pdf
```

## CAPTCHA and Manual Intervention

`CaptchaDetector` looks for:

- reCAPTCHA selectors
- hCaptcha selectors
- Cloudflare challenge selectors
- OTP/security-code inputs
- Security challenge phrases in page text

If detected, platform appliers raise `CaptchaDetectedError`.

`CaptchaHandler` then:

1. Takes a screenshot when possible.
2. Creates an application record with `Manual Intervention Required`.
3. Includes the CAPTCHA type and URL in the failure reason.
4. Sends an immediate email alert through `DailyReporter`.

This code does not solve CAPTCHAs automatically. It stops that application and asks the user to finish manually.

## Database

The database layer lives under `job_agent/database/`.

`migrations.py` defines schema version `1` and creates:

- `schema_version`
- `jobs`
- `applications`
- `run_logs`

The `jobs` table stores discovered jobs and enforces uniqueness by `(platform, job_url)`.

The `applications` table stores every application attempt with:

- `job_id`
- status
- failure reason
- screenshot path
- attempt number
- applied timestamp
- duration in milliseconds

The `run_logs` table stores one row per platform run with:

- start and finish timestamps
- platform
- jobs found
- applied count
- failed count
- skipped count
- manual intervention count
- error message
- run status

`ApplicationRepository` handles:

- Connecting and ensuring schema
- Saving/fetching jobs
- Checking whether a URL has already been successfully applied to
- Saving applications
- Counting today's successful applications by platform
- Producing today's daily report data
- Starting and finishing run logs

SQLite is opened with WAL mode and foreign keys enabled.

## Notifications

Notifications live under `job_agent/notifications/`.

`EmailClient` sends HTML email through SMTP with TLS. It expects Gmail credentials from settings. If email address or app password is missing, it logs a warning and does not send.

`DailyReporter` sends:

- Daily summary emails after a full run
- Immediate CAPTCHA/manual-intervention alerts
- Login expired alerts

`templates.py` builds HTML strings for:

- Daily report table with counts by status
- CAPTCHA/manual intervention alert
- Session expired instructions

## Scripts

`scripts/manual_login.py`

Opens a headed Chromium persistent context for either LinkedIn or Indeed. You log in manually, press Enter in the terminal, and the browser profile is saved to `data/browser_data/<platform>`.

`scripts/reset_cookies.py`

Deletes saved browser session data for `linkedin`, `indeed`, or `all`, then tells you to run `manual_login.py` again.

`scripts/view_report.py`

Reads the SQLite database and prints application reports for today, a specific date, or all time.

`scripts/run_agent.bat`

Activates the virtualenv and runs:

```bat
python -m job_agent.main
```

The batch file now computes the project root from its own script location instead of using a user-specific hardcoded path.

`scripts/setup_scheduler.ps1`

Creates a Windows Scheduled Task named `AIJobApplicationAgent` that runs daily at 9:00 AM. It now computes the batch path, working directory, and scheduler log path from the current project location.

## Tests

The test suite currently covers:

- Settings defaults and helper methods
- SQLite repository operations
- Duplicate job handling
- Application saving
- Daily application counts
- Run log lifecycle
- Daily report query
- Regex-based form field mapping

The tests do not currently cover live Playwright platform automation, live LinkedIn/Indeed DOM behavior, CAPTCHA detection in real pages, email sending, or scheduled-task setup.

## Important Limitations and Risks

- LinkedIn and Indeed selectors are brittle because both sites change their DOM regularly.
- Browser automation against job platforms may violate platform terms of service.
- The code does not solve CAPTCHAs; it detects them and alerts for manual intervention.
- External company career sites vary widely, so external form filling is best-effort.
- Some success detection assumes submission worked after clicking submit if no explicit success indicator is found.
- The `.env` file contains sensitive email/app-password configuration and should not be committed or pasted into documentation.
- `config/profile.yaml` contains personal applicant information and should be treated as private data.
- The Windows scheduler scripts currently point to a different user path and likely need correction before use.
- `venv/` is inside the workspace, so code searches can become noisy unless excluded.

## What Happens When You Run It

Running `python -m job_agent.main` will attempt to use real browser sessions, open real job sites, and potentially submit real job applications. Before running it for real, the project needs:

1. A valid `.env`.
2. A complete `config/profile.yaml`.
3. A resume PDF at the configured `RESUME_PATH`.
4. Saved login sessions created with `scripts/manual_login.py linkedin` and `scripts/manual_login.py indeed`.
5. Review of daily limits and enabled platforms.
6. Path fixes in scheduler scripts if using Windows Task Scheduler.

Once configured, the intended behavior is a daily automated run that searches recent jobs, applies within configured limits, records outcomes, saves screenshots on problems, and emails a summary.

## Safe Auto-Apply Enhancement

The enhancement adds Lahore-only filtering, local resume parsing, deterministic keyword matching, a global 30/day application cap, local template-based writing without an LLM, optional paced employer emails, and Excel reporting under `data/reports/`.

The runtime also has small internal skills under `job_agent/skills/`:

- `JobQualitySkill` rejects unpaid roles and jobs whose stated experience requirement is clearly above the profile.
- `ApplicationAnswerBank` fills common unmapped application questions, such as relocation, visa sponsorship, availability, salary, and "why should we hire you" prompts.

The current runtime also includes a preflight checker:

```bash
python -m job_agent.preflight
```

It blocks real runs until required local inputs are present, including the resume,
valid profile data, enabled-platform sessions, and writable runtime directories.
The default `DRY_RUN` behavior is conservative so first runs can inspect matching
and would-apply decisions before submitting real applications.
