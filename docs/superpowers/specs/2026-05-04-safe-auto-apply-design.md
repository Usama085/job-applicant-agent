# Safe Auto-Apply Enhancement Design

Generated on 2026-05-04.

## Goal

Enhance the existing job application agent so it can automatically apply to only relevant Lahore, Pakistan jobs, match jobs against the user's resume locally without any LLM dependency, pace actions professionally to reduce account risk, generate local template-based application text, optionally send carefully rate-limited employer emails, and export a daily Excel report.

## Non-Goals

- Do not add any cloud LLM or external AI API.
- Do not bypass CAPTCHAs, security checks, or platform restrictions.
- Do not guess employer email addresses.
- Do not scrape hidden/private emails.
- Do not apply outside Lahore, Pakistan.
- Do not send mass email campaigns.
- Do not replace the user's LinkedIn/Indeed accounts or official apply flows.

## External Constraints

Official LinkedIn and Indeed apply APIs are not normal job-seeker APIs. LinkedIn Easy Apply / Apply Connect APIs are restricted to approved partner or ATS integrations. Indeed Apply and Apply with Indeed are also partner/employer/ATS integrations. Because this project is a job-seeker automation tool, the practical auto-apply path remains controlled browser automation through Playwright.

Relevant official references:

- LinkedIn Easy Apply Integration: https://learn.microsoft.com/en-us/linkedin/talent/easy-apply
- LinkedIn Job Posting API Terms: https://www.linkedin.com/legal/l/job-posting-api-terms
- Indeed Apply Partner Docs: https://docs.indeed.com/indeed-apply
- Apply with Indeed: https://docs.indeed.com/indeed-apply/apply-with-indeed

## Recommended Architecture

Keep the current platform-oriented architecture:

- `job_agent/main.py` remains the orchestration entrypoint.
- `job_agent/platforms/base.py` continues to own the common search/filter/apply loop.
- LinkedIn and Indeed remain platform-specific implementations.

Add new focused services:

- `job_agent/matching/resume_parser.py`: extract text from PDF, DOCX, or TXT resumes.
- `job_agent/matching/keyword_extractor.py`: derive local skill/title keywords from resume and job descriptions.
- `job_agent/matching/job_matcher.py`: score whether a job matches the resume and configured target role.
- `job_agent/matching/location_filter.py`: enforce Lahore-only filtering.
- `job_agent/writing/template_writer.py`: generate local cover letters/emails from deterministic templates.
- `job_agent/outreach/email_outreach.py`: send optional employer emails with caps, pauses, duplicate protection, and logging.
- `job_agent/reports/excel_reporter.py`: export daily application/outreach records to XLSX.

Add database fields or tables to track match scores, extracted emails, generated text previews, and employer outreach attempts.

## Configuration

Add these settings to `.env.example` and `Settings`:

```text
GLOBAL_DAILY_APPLICATION_LIMIT=30
TARGET_LOCATIONS=Lahore,Lahore Pakistan,Lahore, Pakistan
STRICT_LOCATION_FILTER=true
MIN_MATCH_SCORE=65
MATCH_REQUIRED_SKILLS=
MATCH_EXCLUDED_KEYWORDS=internship,unpaid,remote only,karachi,islamabad
AUTO_SEND_EMPLOYER_EMAILS=false
MAX_EMPLOYER_EMAILS_PER_DAY=10
MIN_EMAIL_DELAY_MINUTES=8
MAX_EMAIL_DELAY_MINUTES=20
MIN_APPLICATION_DELAY_MINUTES=3
MAX_APPLICATION_DELAY_MINUTES=8
LONG_BREAK_EVERY_APPLICATIONS=5
LONG_BREAK_MINUTES=20
MAX_UNKNOWN_REQUIRED_FIELDS=0
EXPORT_EXCEL_REPORT=true
REPORTS_DIR=./data/reports
```

Default behavior should be conservative:

- Global daily application cap: 30.
- Employer emails disabled until explicitly enabled.
- Lahore-only filtering enabled.
- Resume matching required.
- Unknown required fields cause skip/manual status, not submit.

## Daily Cap

The current system has per-platform limits. Add a global cap so the agent never exceeds 30 successful applications total per local day across LinkedIn and Indeed.

Behavior:

- Count only `Applied` statuses toward the global cap.
- Keep existing platform caps as secondary controls.
- Check the global cap before every application attempt and after every successful application.
- Stop all platforms once the global cap is reached.

## Lahore-Only Filtering

Location filtering must happen in two places:

1. Search queries are forced to Lahore.
2. Scraped job cards and job details are rejected unless their location text matches the configured Lahore aliases.

Default accepted examples:

- `Lahore`
- `Lahore, Punjab`
- `Lahore, Pakistan`
- `Lahore District`

Default rejected examples:

- `Karachi`
- `Islamabad`
- `Rawalpindi`
- `Pakistan Remote`
- `Remote`
- `Hybrid - Karachi`

If a location is missing, mark the job as skipped unless the job detail page clearly confirms Lahore.

## Resume Parsing

The agent should support:

- PDF resumes through `pypdf`.
- Word resumes through `python-docx`.
- Plain text resumes for testing and fallback.

Parsing should happen once per run. If parsing fails or the resume file is missing, the run should stop before searching/applying, because applying without a resume-match signal violates the core requirement.

## Local Resume Matching

The matching engine must be deterministic and local.

Inputs:

- Parsed resume text.
- User profile YAML.
- Search query title.
- Job title.
- Company name.
- Job location.
- Job description text from the job detail page.

Scoring dimensions:

- Title relevance.
- Required skill overlap.
- Resume keyword overlap.
- Lahore location confirmation.
- Experience-level compatibility.
- Excluded keyword rejection.

Suggested starting weights:

- Title match: 25 points.
- Skill overlap: 40 points.
- Resume keyword overlap: 20 points.
- Location confirmation: 10 points.
- Experience compatibility: 5 points.

Minimum default score: 65.

Hard rejection should happen before scoring when:

- Job is outside Lahore.
- Job title clearly does not match the target role family.
- Excluded keywords are present.
- Job requires experience far above profile settings.
- Job details cannot be loaded enough to score.

## Local Template Writing

No LLM should be used.

Add deterministic templates for:

- Cover letter fields inside application forms.
- Optional employer outreach email.

Template variables:

- `{full_name}`
- `{job_title}`
- `{company}`
- `{matched_skills}`
- `{years_experience}`
- `{current_title}`
- `{location}`
- `{linkedin_url}`

Template behavior:

- Pick paragraphs based on matched skills.
- Keep text concise and professional.
- Avoid exaggerated claims.
- Avoid spammy language.
- Include Lahore availability/location where useful.

Example:

```text
Dear Hiring Team,

I am applying for the {job_title} role at {company}. My background matches your requirements in {matched_skills}, and I have hands-on experience supporting cloud infrastructure, automation, CI/CD pipelines, and production operations.

I am based in Lahore and would welcome the opportunity to contribute to your engineering team.

Regards,
{full_name}
```

## Application Safety Gates

Before clicking any final submit/apply button, the agent must verify:

- Global daily application cap has not been reached.
- Platform daily cap has not been reached.
- Job is not a duplicate successful application.
- Job location passes Lahore-only filter.
- Job match score is at or above threshold.
- Resume file exists.
- No CAPTCHA/security signal is present.
- Required fields were filled or are known safe.
- Unknown required fields count is at or below `MAX_UNKNOWN_REQUIRED_FIELDS`.

If a gate fails, save a record with `Skipped` or `Manual Intervention Required`, include the reason, and do not submit.

## Pacing and Ban-Risk Reduction

Add pacing that is slower than the current random short pauses.

Application pacing:

- Random delay between applications: default 3 to 8 minutes.
- Every 5 applications, take a longer break of at least 20 minutes.
- Keep existing human-like typing, scrolling, and click offsets.
- Stop on CAPTCHA/security checks.
- Stop on repeated unexpected failures.

Email pacing:

- Separate random delay between employer emails: default 8 to 20 minutes.
- Separate daily email cap: default 10.
- Do not email the same job/company twice.
- Stop sending outreach emails on repeated SMTP failures.

## Employer Email Detection

Employer emails may not be available on LinkedIn/Indeed. The agent should only capture emails that are visible in:

- Job description text.
- External company application page text.
- Clearly visible contact sections.

The agent must not:

- Guess emails from company names.
- Generate likely address patterns.
- Use third-party enrichment.
- Scrape hidden/private data.

If multiple emails are found, prefer role-specific recruiting addresses such as:

- careers@
- hr@
- recruitment@
- jobs@
- talent@

Reject obvious unrelated emails:

- support@
- privacy@
- legal@
- noreply@
- no-reply@

## Optional Auto Employer Emails

Employer outreach should happen only when:

- `AUTO_SEND_EMPLOYER_EMAILS=true`.
- The job passed Lahore and resume matching gates.
- A visible employer/recruiter email was found.
- The job was successfully applied to or marked as a high-confidence manual opportunity.
- The daily email cap has not been reached.
- This job/company/email combination has not already been contacted.

The email should:

- Use Gmail SMTP through the existing email credentials.
- Use local template text.
- Include a concise subject such as `Application for {job_title} - {full_name}`.
- Log the full result to SQLite and Excel.

Notifications to the user and employer outreach must be separate code paths so daily reports do not accidentally go to employers.

## Excel Report

Export daily XLSX reports to:

```text
data/reports/applications_YYYY-MM-DD.xlsx
```

Columns:

- Date/time.
- Platform.
- Job title.
- Company/employer name.
- Employer/recruiter email if found.
- Location.
- Job URL.
- Apply type.
- Match score.
- Matched skills.
- Generated subject.
- Generated text preview.
- Application status.
- Outreach status.
- Failure/manual reason.

Use `openpyxl` for XLSX output.

## Database Changes

Add fields or tables to support:

- Job description text or snippet.
- Match score.
- Matched keywords.
- Location filter result.
- Apply safety-gate failure reason.
- Employer emails found.
- Outreach attempts.
- Generated email subject/body preview.
- Outreach status and timestamp.

Prefer additive migrations so existing databases are preserved.

## Existing Bug Fixes

Fix these known problems:

- The checked-in `venv` is broken in this workspace because it points to another user's Python installation. Do not rely on it for verification. Document recreating it locally.
- `scripts/run_agent.bat` hardcodes `C:\Users\HamzaAkhtar\Documents\AI Agent`.
- `scripts/setup_scheduler.ps1` hardcodes the same old path.
- Current tests cannot run with the broken `venv`; system Python also lacks `pytest` in this workspace.
- Current platform limits are per-platform only, not the requested global 30/day cap.
- Current search config allows future non-Lahore query expansion; new behavior should enforce Lahore-only by default.

## Testing Strategy

Add unit tests for:

- Resume text parsing from TXT fixture and parser failure behavior.
- Keyword extraction.
- Match scoring.
- Excluded keyword rejection.
- Lahore location acceptance/rejection.
- Global daily cap.
- Safety gates before submit.
- Local template generation.
- Email extraction and filtering.
- Outreach duplicate prevention.
- Excel report output.

Add integration-style tests with mocked platform/job data for:

- Search result filtered out before apply when outside Lahore.
- Job skipped when match score is too low.
- Job applies when all gates pass.
- Employer email sent only when enabled and visible.
- Daily cap stops further applications.

Live browser tests are out of scope for default CI because they depend on external websites and real accounts.

## Rollout Plan

1. Implement matching and location filtering first.
2. Add global daily cap and safety gates.
3. Add local template writer.
4. Add Excel reporting.
5. Add optional employer outreach with conservative defaults.
6. Update scripts, config, docs, and tests.
7. Verify with unit tests and a dry-run mode before enabling real submit/email behavior.

## Dry Run Mode

Add or preserve a dry-run mode before real operation. Dry run should:

- Search and score jobs.
- Detect forms where possible.
- Generate application text.
- Generate report rows.
- Not click final submit buttons.
- Not send employer emails.

This allows safe validation before the first real automated run.

## Open Implementation Decisions

- Whether match threshold should start at `65` or a stricter `70`.
- Whether employer outreach should require a successful platform application or also allow high-confidence manual opportunities.
- Whether to store full generated email bodies in SQLite or only previews plus XLSX output.

Default decisions for implementation:

- Start with `MIN_MATCH_SCORE=65`.
- Send employer outreach only after successful application by default.
- Store generated body previews in the main application report and full body in outreach records.
