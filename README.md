# AI Job Application Agent

Automated job search and application system for LinkedIn and Indeed. The agent searches for DevOps Engineer roles in Lahore, filters by experience level, and automatically applies to matching jobs using browser automation.

## Features

- **Multi-platform**: LinkedIn (Easy Apply + External) and Indeed
- **Smart form filling**: Heuristic field mapping handles arbitrary form layouts
- **Internal skills**: Local job-quality screening and common application answers
- **Anti-detection**: Stealth browser, human-like delays, randomized behavior
- **CAPTCHA handling**: Detects CAPTCHAs and sends you an email alert with the job link
- **Daily automation**: Runs via Windows Task Scheduler at 9:00 AM
- **Email reports**: Daily summary with all application statuses
- **SQLite tracking**: Full history of every job found and application attempted
- **Extensible**: Easy to add new job titles, cities, and platforms

## Prerequisites

- Python 3.11+
- Windows 11 (for Task Scheduler integration)
- Gmail account with [App Password](https://support.google.com/accounts/answer/185833) enabled
- LinkedIn and Indeed accounts

## Quick Start

### 1. Clone and install

```bash
cd "C:\path\to\AI Agent"

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browser
playwright install chromium
```

### 2. Configure

```bash
# Copy environment template
copy .env.example .env
```

Edit `.env` with your settings:
- `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` for email notifications
- `NOTIFICATION_RECIPIENT` for where to send reports
- Keep `DRY_RUN=true` until preflight is clean and you have reviewed dry-run output
- Adjust daily limits, rate limits, and other settings as needed

Edit `config/profile.yaml` with your personal information:
- Name, email, phone, location
- Work experience, current title
- Cover letter template
- Salary expectations, work authorization, etc.

Edit `config/search_queries.yaml` to customize job search:
- Job titles to search for
- Locations
- Experience filters

### 3. Login to platforms

You must log in manually once to save your session cookies:

```bash
# Login to LinkedIn
python scripts/manual_login.py linkedin

# Login to Indeed
python scripts/manual_login.py indeed
```

A browser window opens for each platform. Log in normally, then press Enter in the terminal to save the session.

### 4. Place your resume

Copy your resume PDF to:
```
data/resumes/resume.pdf
```

### 5. Run the agent

Check readiness first:

```bash
python -m job_agent.preflight
```

Preflight must be clean before real runs. It checks the profile, resume path,
saved browser sessions, enabled platforms, and notification settings.

```bash
# Manual run. With DRY_RUN=true, this records would-apply decisions only.
python -m job_agent.main
```

### 6. Set up daily automation (optional)

Open PowerShell as Administrator:
```powershell
cd "C:\path\to\AI Agent"
.\scripts\setup_scheduler.ps1
```

This creates a Windows Scheduled Task that runs the agent daily at 9:00 AM.

## Project Structure

```
AI Agent/
├── job_agent/                  # Main Python package
│   ├── main.py                 # Entry point & orchestration
│   ├── config.py               # Settings from .env
│   ├── browser/                # Browser automation layer
│   │   ├── session.py          # Persistent browser context
│   │   ├── stealth.py          # Anti-detection evasions
│   │   └── humanizer.py        # Human-like behavior simulation
│   ├── platforms/              # Platform implementations
│   │   ├── base.py             # Abstract platform interface
│   │   ├── linkedin/           # LinkedIn search & apply
│   │   └── indeed/             # Indeed search & apply
│   ├── forms/                  # Form detection & auto-fill
│   │   ├── detector.py         # Scan pages for form fields
│   │   ├── filler.py           # Map profile data to fields
│   │   ├── field_mapping.py    # Regex-based heuristic rules
│   │   └── resume_uploader.py  # PDF upload handling
│   ├── captcha/                # CAPTCHA detection & handling
│   ├── database/               # SQLite persistence
│   ├── notifications/          # Email reports & alerts
│   ├── profile/                # User profile management
│   └── utils/                  # Logging, retry, rate limiting
├── config/                     # YAML configuration files
│   ├── profile.yaml            # Your personal info
│   └── search_queries.yaml     # Job search parameters
├── data/                       # Runtime data (gitignored)
│   ├── browser_data/           # Saved browser sessions
│   ├── db/                     # SQLite database
│   ├── logs/                   # Application logs
│   ├── resumes/                # Your resume PDF
│   └── screenshots/            # Debug screenshots
├── scripts/                    # Utility scripts
│   ├── manual_login.py         # Browser login helper
│   ├── run_agent.bat           # Task Scheduler launcher
│   ├── setup_scheduler.ps1     # Create scheduled task
│   ├── view_report.py          # CLI report viewer
│   └── reset_cookies.py        # Clear saved sessions
└── tests/                      # Test suite
```

## Usage

### View today's applications

```bash
python scripts/view_report.py
```

### View all-time stats

```bash
python scripts/view_report.py --all
```

### View a specific date

```bash
python scripts/view_report.py --date 2026-02-17
```

### Reset a platform session

```bash
python scripts/reset_cookies.py linkedin
python scripts/manual_login.py linkedin
```

## Safe Auto-Apply Mode

The agent applies only after these gates pass:

- Lahore-only location filter
- Local resume/job keyword match
- Local job-quality screen for unpaid or clearly over-senior roles
- Global daily cap of 30 successful applications
- Duplicate application check
- CAPTCHA/security check
- Required-field confidence check

The matching, writing, quality screening, and form-answer engine is local and
deterministic. It does not use an LLM.

`DRY_RUN=true` is the safe default. Set `DRY_RUN=false` only after:

- `python -m job_agent.preflight` reports ready
- Your resume exists at `RESUME_PATH`
- LinkedIn/Indeed sessions are saved
- You have reviewed at least one dry-run report

Employer outreach is disabled by default. To enable it:

```env
AUTO_SEND_EMPLOYER_EMAILS=true
MAX_EMPLOYER_EMAILS_PER_DAY=10
```

The agent only sends employer emails when a real visible email address is found in
the job text or application page. It never guesses addresses.

## Configuration Reference

### Environment Variables (.env)

| Variable | Description | Default |
|---|---|---|
| `BROWSER_HEADLESS` | Run browser in headless mode | `false` |
| `LINKEDIN_DAILY_LIMIT` | Max applications per day on LinkedIn | `12` |
| `INDEED_DAILY_LIMIT` | Max applications per day on Indeed | `12` |
| `GMAIL_ADDRESS` | Gmail address for sending notifications | (required) |
| `GMAIL_APP_PASSWORD` | Gmail App Password | (required) |
| `NOTIFICATION_RECIPIENT` | Email to receive reports | (required) |
| `MIN_ACTION_DELAY_MS` | Minimum delay between actions (ms) | `800` |
| `MAX_ACTION_DELAY_MS` | Maximum delay between actions (ms) | `2500` |
| `ENABLED_PLATFORMS` | Comma-separated list of platforms | `linkedin,indeed` |
| `DRY_RUN` | Search/score/report without submitting applications | `true` |
| `GLOBAL_DAILY_APPLICATION_LIMIT` | Max successful applications across all platforms | `30` |
| `MIN_MATCH_SCORE` | Minimum local resume/job match score before applying | `65` |

### Adding New Job Titles or Cities

Edit `config/search_queries.yaml`:

```yaml
queries:
  - title: "DevOps Engineer"
    locations:
      - "Lahore"
      - "Karachi"           # Add new city
    experience_max_years: 3

  - title: "Cloud Engineer"   # Add new title
    locations:
      - "Lahore"
    experience_max_years: 4
```

## How It Works

1. **Session**: Uses Playwright with a persistent browser context. Your login cookies are saved to disk, so you only log in once.

2. **Search**: Navigates to LinkedIn/Indeed job search pages with your configured filters. Extracts job cards with title, company, location, and apply method.

3. **Filter**: Deduplicates against previously applied jobs in the database. Randomly skips ~7% of jobs for anti-detection.

4. **Apply**:
   - LinkedIn Easy Apply: Fills the multi-step modal form automatically
   - External links: Opens company career pages and attempts to fill their forms
   - Indeed: Handles Indeed's apply flow and external redirects

5. **CAPTCHA**: If a CAPTCHA or security check is detected, the agent immediately stops that application, takes a screenshot, and sends you an email with the job link.

6. **Report**: After all platforms are processed, sends a daily summary email with a table of all applications and their statuses.

## Anti-Detection Measures

- `playwright-stealth` patches common bot detection vectors
- Persistent browser context (not fresh sessions)
- Human-like typing with per-character delays
- Random delays between all actions
- Mouse click offset randomization
- Page scrolling simulation
- Randomized platform execution order
- Random job skip rate (anti-pattern detection)
- Circuit breaker: stops after 3 consecutive failures
- Rate limiting per platform

## Troubleshooting

### "Session expired" email

Your login cookies are no longer valid. Run:
```bash
python scripts/manual_login.py <platform>
```

### Agent not finding jobs

- Check `config/search_queries.yaml` for correct job titles and locations
- Check `data/logs/agent.log` for error details
- Try running manually: `python -m job_agent.main`

### Email notifications not working

- Ensure 2FA is enabled on your Gmail account
- Generate an App Password at https://myaccount.google.com/apppasswords
- Verify `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in `.env`

### LinkedIn blocking or CAPTCHA

- Reduce `LINKEDIN_DAILY_LIMIT` to 5-8
- Increase `MIN_ACTION_DELAY_MS` to 1500
- Ensure `BROWSER_HEADLESS=false`

## Disclaimer

This tool automates interactions with LinkedIn and Indeed, which may violate their Terms of Service. Use at your own risk. The authors are not responsible for any account restrictions or other consequences.
