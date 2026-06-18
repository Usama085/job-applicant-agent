# AI Job Application Agent Instructions

This guide explains how to configure, check, and run the local job application agent on Windows with PowerShell.

The agent is local and deterministic. It does not use an LLM. It uses Playwright browser automation, local resume parsing, keyword matching, job-quality screening, safe auto-apply gates, and optional Gmail notifications.

## 1. Open The Project

Open PowerShell and move into the project folder:

```powershell
cd "c:\Users\WaqasArif\Downloads\AI Agent\AI Agent"
```

## 2. Activate The Virtual Environment

Use the working `.venv` folder:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the same PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Confirm Python is coming from `.venv`:

```powershell
python -c "import sys; print(sys.executable)"
```

The path should include:

```text
\.venv\Scripts\python.exe
```

## 3. Install Or Repair Dependencies

If `.venv` already works, you normally do not need this. Run it after moving the project, recreating `.venv`, or seeing import errors.

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## 4. Configure `.env`

The agent reads settings from `.env` in the project root.

If `.env` is missing:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and fill these values.

| Variable | Where To Get Value | Example / Recommended Value |
|---|---|---|
| `BROWSER_HEADLESS` | Browser mode | `false` while testing |
| `BROWSER_SLOW_MO` | Browser delay for visibility | `50` |
| `BROWSER_TIMEOUT_MS` | Browser timeout | `30000` |
| `BROWSER_DATA_DIR` | Saved login sessions | `./data/browser_data` |
| `LINKEDIN_DAILY_LIMIT` | Max LinkedIn successful applies per day | Start with `2`, increase later |
| `INDEED_DAILY_LIMIT` | Max Indeed successful applies per day | Start with `2`, increase later |
| `SMTP_HOST` | Gmail SMTP host | `smtp.gmail.com` |
| `SMTP_PORT` | Gmail SMTP port | `587` |
| `GMAIL_ADDRESS` | Your Gmail sender address | `your.name@gmail.com` |
| `GMAIL_APP_PASSWORD` | Gmail App Password, not normal password | `abcd efgh ijkl mnop` |
| `NOTIFICATION_RECIPIENT` | Email that receives reports/alerts | Your email address |
| `DATABASE_PATH` | SQLite database location | `./data/db/job_agent.db` |
| `RESUME_PATH` | Resume file path | `./data/resumes/resume.pdf` |
| `LOG_LEVEL` | Logging detail | `INFO` |
| `LOG_FILE` | Log file path | `./data/logs/agent.log` |
| `RATE_LIMIT_LINKEDIN_RPM` | LinkedIn actions per minute cap | `20` or lower |
| `RATE_LIMIT_INDEED_RPM` | Indeed actions per minute cap | `15` or lower |
| `MIN_ACTION_DELAY_MS` | Minimum action delay | `800`, safer: `1500` |
| `MAX_ACTION_DELAY_MS` | Maximum action delay | `2500`, safer: `4000` |
| `SCREENSHOT_DIR` | Failure screenshot folder | `./data/screenshots` |
| `SCREENSHOT_ON_FAILURE` | Save screenshots on failures | `true` |
| `ENABLED_PLATFORMS` | Platforms to run | `linkedin,indeed` or only one |
| `GLOBAL_DAILY_APPLICATION_LIMIT` | Total successful applies per day | Start with `4`, later `30` max |
| `TARGET_LOCATIONS` | Allowed locations | `Lahore,Lahore Pakistan,Lahore Punjab,Lahore District` |
| `STRICT_LOCATION_FILTER` | Reject missing/non-Lahore locations | `true` |
| `MIN_MATCH_SCORE` | Resume/job match threshold | `65`, stricter: `70` |
| `MATCH_REQUIRED_SKILLS` | Required skills for every job | Empty, or `docker,kubernetes,aws` |
| `MATCH_EXCLUDED_KEYWORDS` | Hard-reject terms | `internship,unpaid,remote only,karachi,islamabad,rawalpindi` |
| `DRY_RUN` | Do not submit real applications | Keep `true` until ready |
| `MIN_APPLICATION_DELAY_MINUTES` | Delay after successful apply | `3` |
| `MAX_APPLICATION_DELAY_MINUTES` | Max delay after successful apply | `8` |
| `LONG_BREAK_EVERY_APPLICATIONS` | Long break interval | `5` |
| `LONG_BREAK_MINUTES` | Long break duration | `20` |
| `MAX_UNKNOWN_REQUIRED_FIELDS` | Required fields allowed unfilled | `0` |
| `AUTO_SEND_EMPLOYER_EMAILS` | Optional employer outreach | Keep `false` initially |
| `MAX_EMPLOYER_EMAILS_PER_DAY` | Outreach cap | `10` |
| `MIN_EMAIL_DELAY_MINUTES` | Outreach pacing | `8` |
| `MAX_EMAIL_DELAY_MINUTES` | Outreach pacing | `20` |
| `EXPORT_EXCEL_REPORT` | Create Excel report | `true` |
| `REPORTS_DIR` | Excel report folder | `./data/reports` |

Recommended first-run safety values:

```env
DRY_RUN=true
BROWSER_HEADLESS=false
LINKEDIN_DAILY_LIMIT=2
INDEED_DAILY_LIMIT=2
GLOBAL_DAILY_APPLICATION_LIMIT=4
AUTO_SEND_EMPLOYER_EMAILS=false
```

Only set `DRY_RUN=false` after preflight passes and you have reviewed dry-run output.

## 5. Gmail App Password

Email alerts/reports use Gmail SMTP.

You need:

- Gmail account
- 2-step verification enabled
- Gmail App Password

Add these to `.env`:

```env
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
NOTIFICATION_RECIPIENT=your.email@gmail.com
```

Do not use your normal Gmail password.

If email is not configured, the agent can still run, but CAPTCHA/login alerts and daily summary emails will fail.

## 6. Configure `config/profile.yaml`

This file contains the values used to fill application forms.

Fill every important personal field:

```yaml
personal:
  first_name: "Your First Name"
  last_name: "Your Last Name"
  full_name: "Your Full Name"
  email: "your.email@example.com"
  phone: "+92-300-0000000"
  location: "Lahore, Pakistan"
  linkedin_url: "https://www.linkedin.com/in/your-profile"
```

Fill professional details:

```yaml
professional:
  current_title: "DevOps Engineer"
  current_company: "Current or Previous Company"
  years_of_experience: 3
  summary: "Short, truthful summary of your DevOps/cloud/automation experience."
```

Fill application defaults:

```yaml
application_defaults:
  cover_letter: |
    Dear Hiring Team,

    I am interested in the {title} role at {company}. My background is aligned with DevOps, cloud infrastructure, automation, CI/CD, and production operations.

    Regards,
    Your Full Name
  salary_expectation: "Negotiable"
  work_authorization: "Authorized to work in Pakistan"
  visa_sponsorship_required: false
  availability_date: "Immediate"
  willing_to_relocate: false
  notice_period: "Immediate"
```

References are optional. If you do not want to provide references, keep:

```yaml
references: []
```

Remove placeholder emails like `your.email@example.com` before running for real.

## 7. Configure Job Searches

Edit:

```text
config/search_queries.yaml
```

Example:

```yaml
queries:
  - title: "DevOps Engineer"
    locations:
      - "Lahore"
    experience_max_years: 3
    remote_ok: true

  - title: "Cloud Engineer"
    locations:
      - "Lahore"
    experience_max_years: 4
    remote_ok: true
```

Keep Lahore in the search locations if `STRICT_LOCATION_FILTER=true`.

Avoid too many titles at first. Start with one or two.

## 8. Add Your Resume

Default path:

```text
data/resumes/resume.pdf
```

The parser supports:

- `.pdf`
- `.docx`
- `.txt`

If your resume is not a PDF, update `.env`:

```env
RESUME_PATH=./data/resumes/resume.docx
```

Make sure the resume has selectable/extractable text. Scanned image-only PDFs may fail parsing or match poorly.

## 9. Save LinkedIn And Indeed Login Sessions

The agent does not ask for your LinkedIn/Indeed passwords in config. You log in manually once in a browser, and the saved browser session is reused.

Activate `.venv` first:

```powershell
.\.venv\Scripts\Activate.ps1
```

Log in to LinkedIn:

```powershell
python scripts/manual_login.py linkedin
```

What happens:

1. A Chromium browser opens.
2. Log in to LinkedIn normally.
3. Complete any 2FA/security checks.
4. After you are fully logged in, return to PowerShell.
5. Press Enter to save the browser session.

Log in to Indeed:

```powershell
python scripts/manual_login.py indeed
```

Saved sessions are stored under:

```text
data/browser_data/linkedin
data/browser_data/indeed
```

If login expires later:

```powershell
python scripts/reset_cookies.py linkedin
python scripts/manual_login.py linkedin
```

or:

```powershell
python scripts/reset_cookies.py indeed
python scripts/manual_login.py indeed
```

## 10. Run Preflight

Preflight checks required inputs before the agent opens job sites.

```powershell
python -m job_agent.preflight
```

Preflight checks:

- `config/profile.yaml`
- placeholder profile values
- resume exists and can be parsed
- saved browser sessions exist
- enabled platforms are valid
- notification settings
- runtime folders are writable

If preflight says `not ready`, fix the listed blocking issues first.

## 11. Run A Safe Dry Run

Keep this in `.env`:

```env
DRY_RUN=true
```

Then run:

```powershell
python -m job_agent.main
```

In dry run mode, the agent can search, filter, score, and record would-apply decisions, but it should not submit real applications.

Review:

```powershell
python scripts/view_report.py
```

Also check logs:

```powershell
Get-Content .\data\logs\agent.log -Tail 80
```

Check Excel reports if enabled:

```text
data/reports/
```

## 12. Run Real Applications

Only do this after:

- Preflight passes.
- Dry run looks correct.
- Resume matching is finding relevant roles.
- Daily limits are low and safe.
- You understand the platform account risk.

Change `.env`:

```env
DRY_RUN=false
```

Recommended early real-run limits:

```env
LINKEDIN_DAILY_LIMIT=2
INDEED_DAILY_LIMIT=2
GLOBAL_DAILY_APPLICATION_LIMIT=4
MIN_APPLICATION_DELAY_MINUTES=3
MAX_APPLICATION_DELAY_MINUTES=8
```

Run:

```powershell
python -m job_agent.main
```

Watch the browser on the first real run. Keep `BROWSER_HEADLESS=false`.

## 13. Optional Employer Outreach

Default:

```env
AUTO_SEND_EMPLOYER_EMAILS=false
```

Keep it false until normal applications are working well.

To enable later:

```env
AUTO_SEND_EMPLOYER_EMAILS=true
MAX_EMPLOYER_EMAILS_PER_DAY=5
MIN_EMAIL_DELAY_MINUTES=8
MAX_EMAIL_DELAY_MINUTES=20
```

The agent only uses visible email addresses found in job text/application pages. It does not guess email addresses.

## 14. View Reports

Today:

```powershell
python scripts/view_report.py
```

All time:

```powershell
python scripts/view_report.py --all
```

Specific date:

```powershell
python scripts/view_report.py --date 2026-05-19
```

Excel reports:

```text
data/reports/applications_YYYY-MM-DD.xlsx
```

Database:

```text
data/db/job_agent.db
```

Logs:

```text
data/logs/agent.log
```

Screenshots:

```text
data/screenshots/
```

## 15. Set Up Daily Scheduler

Only do this after manual dry run and real run are working.

Open PowerShell as Administrator:

```powershell
cd "c:\Users\WaqasArif\Downloads\AI Agent\AI Agent"
.\scripts\setup_scheduler.ps1
```

This creates a Windows Scheduled Task named:

```text
AIJobApplicationAgent
```

It runs daily at 9:00 AM.

Scheduler output goes to:

```text
data/logs/scheduler.log
```

To run manually from Task Scheduler:

1. Open `taskschd.msc`.
2. Find `AIJobApplicationAgent`.
3. Right-click.
4. Select `Run`.

To remove the task:

```powershell
Unregister-ScheduledTask -TaskName "AIJobApplicationAgent" -Confirm:$false
```

## 16. Useful Maintenance Commands

Run tests:

```powershell
python -m pytest -q
```

Run lint:

```powershell
python -m ruff check job_agent tests scripts
```

Clean generated caches:

```powershell
Remove-Item -LiteralPath ".\.pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ".\.ruff_cache" -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

Check imports:

```powershell
python -B -c "from job_agent.main import main; print('imports ok')"
```

## 17. Troubleshooting

### Preflight says resume missing

Fix one of these:

```env
RESUME_PATH=./data/resumes/resume.pdf
```

or put the resume at:

```text
data/resumes/resume.pdf
```

### Preflight says profile placeholder

Edit:

```text
config/profile.yaml
```

Replace placeholder email, phone, name, LinkedIn URL, and reference values.

### Session expired

Run:

```powershell
python scripts/reset_cookies.py linkedin
python scripts/manual_login.py linkedin
```

or:

```powershell
python scripts/reset_cookies.py indeed
python scripts/manual_login.py indeed
```

### Agent finds irrelevant jobs

Adjust `.env`:

```env
MIN_MATCH_SCORE=70
MATCH_REQUIRED_SKILLS=docker,kubernetes,aws
MATCH_EXCLUDED_KEYWORDS=internship,unpaid,remote only,karachi,islamabad,rawalpindi,senior manager
```

Also narrow:

```text
config/search_queries.yaml
```

### LinkedIn or Indeed shows CAPTCHA

The agent does not solve CAPTCHA. It stops and records manual intervention.

Safer settings:

```env
BROWSER_HEADLESS=false
LINKEDIN_DAILY_LIMIT=2
INDEED_DAILY_LIMIT=2
MIN_ACTION_DELAY_MS=1500
MAX_ACTION_DELAY_MS=4000
MIN_APPLICATION_DELAY_MINUTES=5
MAX_APPLICATION_DELAY_MINUTES=12
```

### Gmail email fails

Check:

```env
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
NOTIFICATION_RECIPIENT=your.email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

Use a Gmail App Password, not the normal account password.

### PowerShell cannot activate `.venv`

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Browser install missing

Run:

```powershell
python -m playwright install chromium
```

## 18. Safe Operating Checklist

Before real auto-apply:

- `.env` is filled.
- `DRY_RUN=true` has already been tested.
- `config/profile.yaml` has no placeholders.
- Resume exists and parses.
- LinkedIn session is saved.
- Indeed session is saved if enabled.
- `python -m job_agent.preflight` reports ready.
- Daily limits are low for first run.
- `BROWSER_HEADLESS=false`.
- You are ready to watch the browser.

Then set:

```env
DRY_RUN=false
```

Run:

```powershell
python -m job_agent.main
```

## 19. Important Risk Note

This agent automates LinkedIn and Indeed interactions through a browser. That may violate platform terms and can trigger account restrictions. Use low limits, keep human review, avoid aggressive schedules, and stop if you see CAPTCHA/security warnings.
