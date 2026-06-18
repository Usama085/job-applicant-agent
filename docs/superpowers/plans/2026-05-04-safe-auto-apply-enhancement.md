# Safe Auto-Apply Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safer auto-apply agent that only applies to Lahore jobs matching the user's resume, caps successful applications at 30/day, writes local template-based text without an LLM, optionally sends paced employer emails, and exports an Excel report.

**Architecture:** Keep the existing Playwright platform layer for LinkedIn/Indeed applying, but add deterministic pre-apply services for resume parsing, keyword matching, location filtering, safety gates, outreach, and reporting. The platform loop will call these services before any final submit action, and all decisions will be recorded in SQLite and XLSX output.

**Tech Stack:** Python 3.11+, Playwright, SQLite, PyYAML, python-dotenv, pypdf, python-docx, openpyxl, pytest.

---

## File Structure

Create:

- `job_agent/matching/__init__.py`: package marker.
- `job_agent/matching/resume_parser.py`: extract local resume text from PDF, DOCX, and TXT.
- `job_agent/matching/keyword_extractor.py`: normalize text and extract known tech/job keywords.
- `job_agent/matching/location_filter.py`: enforce Lahore-only location rules.
- `job_agent/matching/job_matcher.py`: score job fit against resume/profile/search intent.
- `job_agent/policy/__init__.py`: package marker.
- `job_agent/policy/application_policy.py`: combine global cap, location, score, duplicate, and field gates.
- `job_agent/writing/__init__.py`: package marker.
- `job_agent/writing/template_writer.py`: local deterministic cover-letter and employer-email generation.
- `job_agent/outreach/__init__.py`: package marker.
- `job_agent/outreach/email_extractor.py`: extract visible employer emails from page/job text.
- `job_agent/outreach/email_outreach.py`: paced optional employer outreach with duplicate prevention.
- `job_agent/reports/__init__.py`: package marker.
- `job_agent/reports/excel_reporter.py`: export daily XLSX report.
- `tests/test_matching/__init__.py`
- `tests/test_matching/test_location_filter.py`
- `tests/test_matching/test_resume_parser.py`
- `tests/test_matching/test_keyword_extractor.py`
- `tests/test_matching/test_job_matcher.py`
- `tests/test_policy/__init__.py`
- `tests/test_policy/test_application_policy.py`
- `tests/test_writing/__init__.py`
- `tests/test_writing/test_template_writer.py`
- `tests/test_outreach/__init__.py`
- `tests/test_outreach/test_email_extractor.py`
- `tests/test_reports/__init__.py`
- `tests/test_reports/test_excel_reporter.py`

Modify:

- `requirements.txt`: add `pypdf`, `python-docx`, `openpyxl`.
- `pyproject.toml`: add the same dependencies.
- `.env.example`: add safe-apply, matching, pacing, outreach, and report settings.
- `job_agent/config.py`: add typed settings fields.
- `job_agent/database/migrations.py`: add schema version 2 with additive columns/tables.
- `job_agent/database/models.py`: extend models and add outreach model.
- `job_agent/database/repository.py`: add global cap, match metadata, email/outreach, and report queries.
- `job_agent/main.py`: initialize new services and export report after run.
- `job_agent/platforms/base.py`: enforce global policy and paced application loop.
- `job_agent/platforms/linkedin/applier.py`: expose job detail text/email source and use generated text.
- `job_agent/platforms/indeed/applier.py`: expose job detail text/email source and use generated text.
- `job_agent/forms/filler.py`: return richer fill results for safety gates.
- `scripts/run_agent.bat`: remove hardcoded old user path.
- `scripts/setup_scheduler.ps1`: compute paths from script location.
- `README.md`: document safer workflow, local resume matching, dry run, and outreach controls.
- `details.md`: optionally append a short note that the codebase now has a safe-apply plan.

Verification environment note:

- The checked-in `venv` is broken in this workspace and points to another user path. Use system Python after installing dev dependencies, or recreate the venv with `python -m venv venv`.

---

### Task 1: Dependency And Settings Foundation

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `job_agent/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add failing settings tests**

Append these tests to `tests/test_config.py`:

```python
def test_safe_apply_settings_defaults():
    settings = Settings.from_env()
    assert settings.global_daily_application_limit == 30
    assert settings.strict_location_filter is True
    assert settings.min_match_score == 65
    assert settings.auto_send_employer_emails is False
    assert settings.max_employer_emails_per_day == 10
    assert settings.export_excel_report is True
    assert settings.reports_dir.name == "reports"


def test_target_locations_and_excluded_keywords_are_lists():
    settings = Settings.from_env()
    assert "Lahore" in settings.target_locations
    assert "karachi" in settings.match_excluded_keywords
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected before implementation: FAIL with `AttributeError` for `global_daily_application_limit`.

- [ ] **Step 3: Add dependencies**

Update `requirements.txt` to:

```text
playwright==1.49.1
playwright-stealth==2.0.2
python-dotenv==1.0.1
pyyaml==6.0.2
tenacity==9.0.0
pydantic==2.10.0
pypdf==5.1.0
python-docx==1.1.2
openpyxl==3.1.5
```

In `pyproject.toml`, add these dependency strings inside `[project].dependencies`:

```toml
    "pypdf>=5.1.0",
    "python-docx>=1.1.2",
    "openpyxl>=3.1.5",
```

- [ ] **Step 4: Add environment defaults**

Append to `.env.example`:

```text
# --- Safe Auto-Apply ---
GLOBAL_DAILY_APPLICATION_LIMIT=30
TARGET_LOCATIONS=Lahore,Lahore Pakistan,Lahore, Pakistan
STRICT_LOCATION_FILTER=true
MIN_MATCH_SCORE=65
MATCH_REQUIRED_SKILLS=
MATCH_EXCLUDED_KEYWORDS=internship,unpaid,remote only,karachi,islamabad,rawalpindi
DRY_RUN=false

# --- Application Pacing ---
MIN_APPLICATION_DELAY_MINUTES=3
MAX_APPLICATION_DELAY_MINUTES=8
LONG_BREAK_EVERY_APPLICATIONS=5
LONG_BREAK_MINUTES=20
MAX_UNKNOWN_REQUIRED_FIELDS=0

# --- Employer Outreach ---
AUTO_SEND_EMPLOYER_EMAILS=false
MAX_EMPLOYER_EMAILS_PER_DAY=10
MIN_EMAIL_DELAY_MINUTES=8
MAX_EMAIL_DELAY_MINUTES=20

# --- Reports ---
EXPORT_EXCEL_REPORT=true
REPORTS_DIR=./data/reports
```

- [ ] **Step 5: Extend Settings**

In `job_agent/config.py`, add fields to the `Settings` dataclass after `enabled_platforms`:

```python
    # Safe auto-apply
    global_daily_application_limit: int = 30
    target_locations: list[str] = field(default_factory=list)
    strict_location_filter: bool = True
    min_match_score: int = 65
    match_required_skills: list[str] = field(default_factory=list)
    match_excluded_keywords: list[str] = field(default_factory=list)
    dry_run: bool = False

    # Application pacing
    min_application_delay_minutes: int = 3
    max_application_delay_minutes: int = 8
    long_break_every_applications: int = 5
    long_break_minutes: int = 20
    max_unknown_required_fields: int = 0

    # Employer outreach
    auto_send_employer_emails: bool = False
    max_employer_emails_per_day: int = 10
    min_email_delay_minutes: int = 8
    max_email_delay_minutes: int = 20

    # Reports
    export_excel_report: bool = True
    reports_dir: Path = Path("./data/reports").resolve()
```

Then add constructor values in `from_env()`:

```python
            global_daily_application_limit=_int(get("GLOBAL_DAILY_APPLICATION_LIMIT", "30")),
            target_locations=_str_list(get("TARGET_LOCATIONS", "Lahore,Lahore Pakistan,Lahore, Pakistan")),
            strict_location_filter=_bool(get("STRICT_LOCATION_FILTER", "true")),
            min_match_score=_int(get("MIN_MATCH_SCORE", "65")),
            match_required_skills=_str_list(get("MATCH_REQUIRED_SKILLS", "")),
            match_excluded_keywords=_str_list(
                get("MATCH_EXCLUDED_KEYWORDS", "internship,unpaid,remote only,karachi,islamabad,rawalpindi")
            ),
            dry_run=_bool(get("DRY_RUN", "false")),
            min_application_delay_minutes=_int(get("MIN_APPLICATION_DELAY_MINUTES", "3")),
            max_application_delay_minutes=_int(get("MAX_APPLICATION_DELAY_MINUTES", "8")),
            long_break_every_applications=_int(get("LONG_BREAK_EVERY_APPLICATIONS", "5")),
            long_break_minutes=_int(get("LONG_BREAK_MINUTES", "20")),
            max_unknown_required_fields=_int(get("MAX_UNKNOWN_REQUIRED_FIELDS", "0")),
            auto_send_employer_emails=_bool(get("AUTO_SEND_EMPLOYER_EMAILS", "false")),
            max_employer_emails_per_day=_int(get("MAX_EMPLOYER_EMAILS_PER_DAY", "10")),
            min_email_delay_minutes=_int(get("MIN_EMAIL_DELAY_MINUTES", "8")),
            max_email_delay_minutes=_int(get("MAX_EMAIL_DELAY_MINUTES", "20")),
            export_excel_report=_bool(get("EXPORT_EXCEL_REPORT", "true")),
            reports_dir=_path(get("REPORTS_DIR", "./data/reports")),
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected after implementation: PASS for all config tests.

- [ ] **Step 7: Version-control checkpoint**

Run:

```bash
git status --short
```

If this workspace is inside a git repository, commit:

```bash
git add requirements.txt pyproject.toml .env.example job_agent/config.py tests/test_config.py
git commit -m "feat: add safe auto apply settings"
```

If `git status` reports this is not a git repository, record that fact in the implementation notes and continue.

---

### Task 2: Resume Parsing

**Files:**
- Create: `job_agent/matching/__init__.py`
- Create: `job_agent/matching/resume_parser.py`
- Create: `tests/test_matching/__init__.py`
- Create: `tests/test_matching/test_resume_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_matching/test_resume_parser.py`:

```python
from pathlib import Path

import pytest

from job_agent.matching.resume_parser import ResumeParser, ResumeParseError


def test_parse_txt_resume(tmp_path: Path):
    resume = tmp_path / "resume.txt"
    resume.write_text("DevOps Engineer\nPython Docker Kubernetes Lahore", encoding="utf-8")

    parser = ResumeParser()
    text = parser.parse(resume)

    assert "DevOps Engineer" in text
    assert "Kubernetes" in text


def test_missing_resume_raises(tmp_path: Path):
    parser = ResumeParser()

    with pytest.raises(ResumeParseError, match="Resume file not found"):
        parser.parse(tmp_path / "missing.pdf")


def test_unsupported_resume_type_raises(tmp_path: Path):
    resume = tmp_path / "resume.rtf"
    resume.write_text("content", encoding="utf-8")
    parser = ResumeParser()

    with pytest.raises(ResumeParseError, match="Unsupported resume format"):
        parser.parse(resume)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_matching/test_resume_parser.py -v
```

Expected before implementation: FAIL with `ModuleNotFoundError: No module named 'job_agent.matching'`.

- [ ] **Step 3: Implement parser**

Create empty `job_agent/matching/__init__.py`.

Create `job_agent/matching/resume_parser.py`:

```python
"""Local resume text extraction for PDF, DOCX, and TXT files."""

from __future__ import annotations

from pathlib import Path


class ResumeParseError(Exception):
    """Raised when a resume cannot be loaded or parsed."""


class ResumeParser:
    """Extracts plain text from supported local resume formats."""

    SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}

    def parse(self, path: Path) -> str:
        resume_path = path.expanduser().resolve()
        if not resume_path.exists():
            raise ResumeParseError(f"Resume file not found: {resume_path}")

        suffix = resume_path.suffix.lower()
        if suffix == ".txt":
            return self._parse_txt(resume_path)
        if suffix == ".pdf":
            return self._parse_pdf(resume_path)
        if suffix == ".docx":
            return self._parse_docx(resume_path)

        supported = ", ".join(sorted(self.SUPPORTED_SUFFIXES))
        raise ResumeParseError(
            f"Unsupported resume format '{suffix}'. Supported formats: {supported}"
        )

    @staticmethod
    def _parse_txt(path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ResumeParser._clean_text(text)

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ResumeParseError("pypdf is required to parse PDF resumes") from exc

        try:
            reader = PdfReader(str(path))
            parts = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise ResumeParseError(f"Failed to parse PDF resume: {exc}") from exc

        text = ResumeParser._clean_text("\n".join(parts))
        if not text:
            raise ResumeParseError("PDF resume did not contain extractable text")
        return text

    @staticmethod
    def _parse_docx(path: Path) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise ResumeParseError("python-docx is required to parse DOCX resumes") from exc

        try:
            document = Document(str(path))
            parts = [paragraph.text for paragraph in document.paragraphs]
        except Exception as exc:
            raise ResumeParseError(f"Failed to parse DOCX resume: {exc}") from exc

        text = ResumeParser._clean_text("\n".join(parts))
        if not text:
            raise ResumeParseError("DOCX resume did not contain extractable text")
        return text

    @staticmethod
    def _clean_text(text: str) -> str:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
python -m pytest tests/test_matching/test_resume_parser.py -v
```

Expected after implementation: PASS.

- [ ] **Step 5: Version-control checkpoint**

Run:

```bash
git status --short
```

If git is available:

```bash
git add job_agent/matching tests/test_matching
git commit -m "feat: parse local resumes"
```

---

### Task 3: Keyword Extraction And Lahore Location Filter

**Files:**
- Create: `job_agent/matching/keyword_extractor.py`
- Create: `job_agent/matching/location_filter.py`
- Create: `tests/test_matching/test_keyword_extractor.py`
- Create: `tests/test_matching/test_location_filter.py`

- [ ] **Step 1: Write failing keyword tests**

Create `tests/test_matching/test_keyword_extractor.py`:

```python
from job_agent.matching.keyword_extractor import KeywordExtractor


def test_extract_known_technical_keywords():
    extractor = KeywordExtractor()
    keywords = extractor.extract(
        "DevOps Engineer with Python, Docker, Kubernetes, AWS, CI/CD and Terraform."
    )

    assert "devops" in keywords
    assert "python" in keywords
    assert "docker" in keywords
    assert "kubernetes" in keywords
    assert "terraform" in keywords


def test_extract_returns_sorted_unique_keywords():
    extractor = KeywordExtractor()
    keywords = extractor.extract("Docker docker DOCKER Kubernetes")

    assert keywords == ["docker", "kubernetes"]
```

- [ ] **Step 2: Write failing location tests**

Create `tests/test_matching/test_location_filter.py`:

```python
from job_agent.matching.location_filter import LocationFilter


def test_accepts_lahore_locations():
    location_filter = LocationFilter(["Lahore", "Lahore Pakistan", "Lahore, Pakistan"])

    assert location_filter.is_allowed("Lahore")
    assert location_filter.is_allowed("Lahore, Punjab, Pakistan")
    assert location_filter.is_allowed("Hybrid - Lahore")


def test_rejects_non_lahore_locations():
    location_filter = LocationFilter(["Lahore"])

    assert not location_filter.is_allowed("Karachi")
    assert not location_filter.is_allowed("Islamabad, Pakistan")
    assert not location_filter.is_allowed("Remote - Pakistan")


def test_missing_location_is_rejected_when_strict():
    location_filter = LocationFilter(["Lahore"], strict=True)

    assert not location_filter.is_allowed(None)
    assert not location_filter.is_allowed("")


def test_missing_location_is_allowed_when_not_strict():
    location_filter = LocationFilter(["Lahore"], strict=False)

    assert location_filter.is_allowed(None)
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
python -m pytest tests/test_matching/test_keyword_extractor.py tests/test_matching/test_location_filter.py -v
```

Expected before implementation: FAIL with import errors.

- [ ] **Step 4: Implement keyword extractor**

Create `job_agent/matching/keyword_extractor.py`:

```python
"""Deterministic keyword extraction for resume and job matching."""

from __future__ import annotations

import re


class KeywordExtractor:
    """Extracts a stable set of known technical and role keywords."""

    DEFAULT_KEYWORDS = {
        "ansible",
        "aws",
        "azure",
        "bash",
        "ci/cd",
        "cloud",
        "devops",
        "docker",
        "gcp",
        "git",
        "github actions",
        "gitlab",
        "grafana",
        "jenkins",
        "kubernetes",
        "linux",
        "monitoring",
        "nginx",
        "prometheus",
        "python",
        "scripting",
        "terraform",
        "windows server",
    }

    def __init__(self, extra_keywords: list[str] | None = None):
        self.keywords = set(self.DEFAULT_KEYWORDS)
        if extra_keywords:
            self.keywords.update(k.strip().lower() for k in extra_keywords if k.strip())

    def extract(self, text: str) -> list[str]:
        normalized = self.normalize(text)
        found = []
        for keyword in self.keywords:
            pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
            if re.search(pattern, normalized):
                found.append(keyword)
        return sorted(set(found))

    @staticmethod
    def normalize(text: str) -> str:
        lowered = text.lower()
        lowered = lowered.replace("cicd", "ci/cd")
        lowered = re.sub(r"[\s_]+", " ", lowered)
        return lowered
```

- [ ] **Step 5: Implement location filter**

Create `job_agent/matching/location_filter.py`:

```python
"""Location filtering for Lahore-only job targeting."""

from __future__ import annotations


class LocationFilter:
    """Allows jobs only when their visible location matches configured targets."""

    BLOCKED_TERMS = {"karachi", "islamabad", "rawalpindi", "faisalabad", "remote"}

    def __init__(self, allowed_locations: list[str], strict: bool = True):
        self.strict = strict
        self.allowed_locations = [
            self._normalize(location)
            for location in allowed_locations
            if location and location.strip()
        ]

    def is_allowed(self, location: str | None) -> bool:
        if not location or not location.strip():
            return not self.strict

        normalized = self._normalize(location)
        if any(term in normalized for term in self.BLOCKED_TERMS):
            return "lahore" in normalized and "remote" not in normalized

        return any(allowed in normalized or normalized in allowed for allowed in self.allowed_locations)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.lower().replace(",", " ").split())
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_matching/test_keyword_extractor.py tests/test_matching/test_location_filter.py -v
```

Expected after implementation: PASS.

---

### Task 4: Local Job Matcher

**Files:**
- Create: `job_agent/matching/job_matcher.py`
- Create: `tests/test_matching/test_job_matcher.py`

- [ ] **Step 1: Write failing matcher tests**

Create `tests/test_matching/test_job_matcher.py`:

```python
from job_agent.database.models import Job
from job_agent.matching.job_matcher import JobMatcher
from job_agent.platforms.base import SearchQuery
from job_agent.profile.user_profile import UserProfile


def _profile() -> UserProfile:
    return UserProfile(
        first_name="Test",
        last_name="User",
        full_name="Test User",
        email="test@example.com",
        phone="+92-300-1234567",
        location="Lahore, Pakistan",
        linkedin_url="https://linkedin.com/in/test",
        current_title="DevOps Engineer",
        current_company="Example",
        years_of_experience=3,
        summary="DevOps engineer with Docker Kubernetes AWS Terraform CI/CD Linux.",
        cover_letter="Dear {company}, I am interested in {title}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=False,
        notice_period="Immediate",
    )


def test_high_score_for_matching_lahore_devops_job():
    matcher = JobMatcher(min_score=65, excluded_keywords=["karachi"])
    job = Job(
        platform="linkedin",
        title="DevOps Engineer",
        company="Acme",
        location="Lahore, Pakistan",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform CI/CD Linux DevOps",
        job_description="We need Docker, Kubernetes, AWS, Terraform and CI/CD.",
    )

    assert result.allowed
    assert result.score >= 65
    assert "docker" in result.matched_keywords


def test_rejects_excluded_location_keyword():
    matcher = JobMatcher(min_score=65, excluded_keywords=["karachi"])
    job = Job(
        platform="indeed",
        title="DevOps Engineer",
        company="Acme",
        location="Karachi",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform",
        job_description="Karachi based DevOps role with Docker.",
    )

    assert not result.allowed
    assert "excluded keyword" in result.reason.lower()


def test_rejects_low_score_job():
    matcher = JobMatcher(min_score=65, excluded_keywords=[])
    job = Job(
        platform="linkedin",
        title="Sales Executive",
        company="Acme",
        location="Lahore",
        job_url="https://example.com/job",
    )
    query = SearchQuery(title="DevOps Engineer", location="Lahore")

    result = matcher.score(
        job=job,
        query=query,
        profile=_profile(),
        resume_text="Docker Kubernetes AWS Terraform",
        job_description="Sales role with customer calls.",
    )

    assert not result.allowed
    assert result.score < 65
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_matching/test_job_matcher.py -v
```

Expected before implementation: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement matcher**

Create `job_agent/matching/job_matcher.py`:

```python
"""Local deterministic job-to-resume matching."""

from __future__ import annotations

from dataclasses import dataclass, field

from job_agent.database.models import Job
from job_agent.matching.keyword_extractor import KeywordExtractor
from job_agent.platforms.base import SearchQuery
from job_agent.profile.user_profile import UserProfile


@dataclass
class MatchResult:
    allowed: bool
    score: int
    matched_keywords: list[str] = field(default_factory=list)
    reason: str = ""


class JobMatcher:
    """Scores job relevance using local keywords and simple deterministic rules."""

    def __init__(
        self,
        min_score: int,
        excluded_keywords: list[str],
        required_skills: list[str] | None = None,
    ):
        self.min_score = min_score
        self.excluded_keywords = [k.lower() for k in excluded_keywords if k]
        self.required_skills = [k.lower() for k in (required_skills or []) if k]
        self.extractor = KeywordExtractor(extra_keywords=self.required_skills)

    def score(
        self,
        job: Job,
        query: SearchQuery,
        profile: UserProfile,
        resume_text: str,
        job_description: str,
    ) -> MatchResult:
        combined_job_text = " ".join(
            [
                job.title or "",
                job.company or "",
                job.location or "",
                job_description or "",
            ]
        ).lower()

        for excluded in self.excluded_keywords:
            if excluded and excluded in combined_job_text:
                return MatchResult(False, 0, [], f"Excluded keyword found: {excluded}")

        resume_keywords = set(self.extractor.extract(resume_text))
        job_keywords = set(self.extractor.extract(combined_job_text))
        matched = sorted(resume_keywords & job_keywords)

        score = 0

        title_text = f"{job.title or ''} {query.title}".lower()
        if "devops" in title_text:
            score += 25
        elif any(token in title_text for token in ("cloud", "platform", "sre", "site reliability")):
            score += 15

        if job_keywords:
            score += min(40, int((len(matched) / max(len(job_keywords), 1)) * 40))

        if resume_keywords:
            score += min(20, int((len(matched) / max(len(resume_keywords), 1)) * 20))

        if "lahore" in (job.location or "").lower():
            score += 10

        years_text = combined_job_text
        if str(profile.years_of_experience) in years_text or "entry" in years_text or "junior" in years_text:
            score += 5
        elif profile.years_of_experience >= 3 and any(term in years_text for term in ("2 years", "3 years", "2+ years", "3+ years")):
            score += 5

        missing_required = [skill for skill in self.required_skills if skill not in matched]
        if missing_required:
            return MatchResult(False, score, matched, f"Missing required skills: {', '.join(missing_required)}")

        allowed = score >= self.min_score
        reason = "Matched resume threshold" if allowed else f"Match score {score} below threshold {self.min_score}"
        return MatchResult(allowed, score, matched, reason)
```

- [ ] **Step 4: Run matcher tests**

Run:

```bash
python -m pytest tests/test_matching/test_job_matcher.py -v
```

Expected after implementation: PASS.

---

### Task 5: Database Schema And Repository Support

**Files:**
- Modify: `job_agent/database/migrations.py`
- Modify: `job_agent/database/models.py`
- Modify: `job_agent/database/repository.py`
- Test: `tests/test_database/test_repository.py`

- [ ] **Step 1: Add failing repository tests**

Append to `tests/test_database/test_repository.py`:

```python
def test_global_today_count(repository: ApplicationRepository):
    linkedin = Job(platform="linkedin", title="DevOps", job_url="https://example.com/li")
    indeed = Job(platform="indeed", title="DevOps", job_url="https://example.com/in")
    li_id = repository.save_job(linkedin)
    in_id = repository.save_job(indeed)
    repository.save_application(Application(job_id=li_id, status=ApplicationStatus.APPLIED))
    repository.save_application(Application(job_id=in_id, status=ApplicationStatus.APPLIED))

    assert repository.get_global_today_count() == 2


def test_update_job_match_metadata(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com/match")
    job_id = repository.save_job(job)

    repository.update_job_match(
        job_id=job_id,
        job_description="Docker Kubernetes Lahore",
        match_score=82,
        matched_keywords=["docker", "kubernetes"],
        location_allowed=True,
        safety_reason="Matched resume threshold",
    )

    report = repository.get_daily_report()
    assert report == []


def test_outreach_lifecycle(repository: ApplicationRepository):
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com/outreach")
    job_id = repository.save_job(job)

    outreach_id = repository.save_outreach(
        job_id=job_id,
        recipient="hr@example.com",
        subject="Application for DevOps",
        body="Dear Hiring Team",
        status="Sent",
        failure_reason=None,
    )

    assert outreach_id > 0
    assert repository.was_email_contacted(job_id, "hr@example.com")
    assert repository.get_today_outreach_count() == 1
```

- [ ] **Step 2: Run failing repository tests**

Run:

```bash
python -m pytest tests/test_database/test_repository.py -v
```

Expected before implementation: FAIL with missing repository methods.

- [ ] **Step 3: Add schema version 2**

In `job_agent/database/migrations.py`, change:

```python
SCHEMA_VERSION = 2
```

Add this migration helper below `SCHEMA_SQL`:

```python
MIGRATION_2_SQL = """
ALTER TABLE jobs ADD COLUMN job_description TEXT;
ALTER TABLE jobs ADD COLUMN match_score INTEGER;
ALTER TABLE jobs ADD COLUMN matched_keywords TEXT;
ALTER TABLE jobs ADD COLUMN location_allowed INTEGER;
ALTER TABLE jobs ADD COLUMN safety_reason TEXT;

CREATE TABLE IF NOT EXISTS outreach_emails (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    recipient       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('Sent', 'Failed', 'Skipped')),
    failure_reason  TEXT,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(job_id, recipient)
);

CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_emails(sent_at);
CREATE INDEX IF NOT EXISTS idx_outreach_job_id ON outreach_emails(job_id);
"""
```

Then update `ensure_schema()` version upgrade block:

```python
    if current_version < SCHEMA_VERSION:
        logger.info(
            "Upgrading database schema from version %d to %d",
            current_version,
            SCHEMA_VERSION,
        )
        if current_version < 2:
            for statement in MIGRATION_2_SQL.strip().split(";"):
                sql = statement.strip()
                if not sql:
                    continue
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
        conn.commit()
        logger.info("Database schema upgraded successfully")
```

Also add the same new columns and `outreach_emails` table to `SCHEMA_SQL` so fresh databases have version 2 directly.

- [ ] **Step 4: Add OutreachEmail model**

Append to `job_agent/database/models.py`:

```python
@dataclass
class OutreachEmail:
    job_id: int
    recipient: str
    subject: str
    body: str
    status: str
    id: int | None = None
    failure_reason: str | None = None
    sent_at: datetime = field(default_factory=datetime.now)
```

- [ ] **Step 5: Add repository methods**

In `job_agent/database/repository.py`, import `json` and add:

```python
import json
```

Add methods inside `ApplicationRepository`:

```python
    def get_global_today_count(self) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM applications
            WHERE status = ? AND date(applied_at) = date('now')
            """,
            (ApplicationStatus.APPLIED.value,),
        ).fetchone()
        return row["cnt"] if row else 0

    def update_job_match(
        self,
        job_id: int,
        job_description: str,
        match_score: int,
        matched_keywords: list[str],
        location_allowed: bool,
        safety_reason: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE jobs SET
                job_description = ?,
                match_score = ?,
                matched_keywords = ?,
                location_allowed = ?,
                safety_reason = ?
            WHERE id = ?
            """,
            (
                job_description,
                match_score,
                json.dumps(matched_keywords),
                int(location_allowed),
                safety_reason,
                job_id,
            ),
        )
        self.conn.commit()

    def save_outreach(
        self,
        job_id: int,
        recipient: str,
        subject: str,
        body: str,
        status: str,
        failure_reason: str | None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO outreach_emails
                (job_id, recipient, subject, body, status, failure_reason, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                recipient,
                subject,
                body,
                status,
                failure_reason,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def was_email_contacted(self, job_id: int, recipient: str) -> bool:
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM outreach_emails
            WHERE job_id = ? AND lower(recipient) = lower(?)
            """,
            (job_id, recipient),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    def get_today_outreach_count(self) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) as cnt FROM outreach_emails
            WHERE status = 'Sent' AND date(sent_at) = date('now')
            """
        ).fetchone()
        return row["cnt"] if row else 0

    def get_daily_export_rows(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT j.title, j.company, j.location, j.platform, j.job_url,
                   j.is_easy_apply, j.is_external, j.match_score,
                   j.matched_keywords, j.safety_reason,
                   a.applied_at, a.status as application_status,
                   a.failure_reason as application_reason,
                   o.recipient, o.subject, o.body,
                   o.status as outreach_status, o.failure_reason as outreach_reason,
                   o.sent_at
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            LEFT JOIN outreach_emails o ON o.job_id = j.id
            WHERE date(a.applied_at) = date('now')
            ORDER BY a.applied_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 6: Run repository tests**

Run:

```bash
python -m pytest tests/test_database/test_repository.py -v
```

Expected after implementation: PASS.

---

### Task 6: Application Policy And Safety Gates

**Files:**
- Create: `job_agent/policy/__init__.py`
- Create: `job_agent/policy/application_policy.py`
- Create: `tests/test_policy/__init__.py`
- Create: `tests/test_policy/test_application_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create `tests/test_policy/test_application_policy.py`:

```python
from dataclasses import dataclass

from job_agent.database.models import Job
from job_agent.matching.job_matcher import MatchResult
from job_agent.policy.application_policy import ApplicationPolicy, PolicyDecision


@dataclass
class FakeRepository:
    global_count: int = 0
    duplicate: bool = False

    def get_global_today_count(self) -> int:
        return self.global_count

    def is_already_applied(self, job_url: str) -> bool:
        return self.duplicate


def test_blocks_when_global_cap_reached():
    policy = ApplicationPolicy(repository=FakeRepository(global_count=30), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "Global daily application limit reached"


def test_blocks_duplicate_successful_application():
    policy = ApplicationPolicy(repository=FakeRepository(duplicate=True), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "Already successfully applied to this job"


def test_blocks_low_match_result():
    policy = ApplicationPolicy(repository=FakeRepository(), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(False, 40, [], "low score"), unknown_required_fields=0)

    assert not decision.allowed
    assert decision.status_reason == "low score"


def test_blocks_unknown_required_fields():
    policy = ApplicationPolicy(
        repository=FakeRepository(),
        global_daily_limit=30,
        max_unknown_required_fields=0,
    )
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=1)

    assert not decision.allowed
    assert decision.status_reason == "Unknown required fields: 1"


def test_allows_when_all_gates_pass():
    policy = ApplicationPolicy(repository=FakeRepository(), global_daily_limit=30)
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com", location="Lahore")

    decision = policy.evaluate(job, MatchResult(True, 80, ["docker"], "ok"), unknown_required_fields=0)

    assert decision == PolicyDecision(True, "Allowed")
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_policy/test_application_policy.py -v
```

Expected before implementation: FAIL with import errors.

- [ ] **Step 3: Implement policy**

Create empty `job_agent/policy/__init__.py`.

Create `job_agent/policy/application_policy.py`:

```python
"""Pre-submit safety policy for auto applications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_agent.database.models import Job
from job_agent.matching.job_matcher import MatchResult


class PolicyRepository(Protocol):
    def get_global_today_count(self) -> int: ...
    def is_already_applied(self, job_url: str) -> bool: ...


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    status_reason: str


class ApplicationPolicy:
    """Combines caps, duplicate checks, match results, and field confidence."""

    def __init__(
        self,
        repository: PolicyRepository,
        global_daily_limit: int,
        max_unknown_required_fields: int = 0,
    ):
        self.repository = repository
        self.global_daily_limit = global_daily_limit
        self.max_unknown_required_fields = max_unknown_required_fields

    def evaluate(
        self,
        job: Job,
        match_result: MatchResult,
        unknown_required_fields: int,
    ) -> PolicyDecision:
        if self.repository.get_global_today_count() >= self.global_daily_limit:
            return PolicyDecision(False, "Global daily application limit reached")

        if self.repository.is_already_applied(job.job_url):
            return PolicyDecision(False, "Already successfully applied to this job")

        if not match_result.allowed:
            return PolicyDecision(False, match_result.reason)

        if unknown_required_fields > self.max_unknown_required_fields:
            return PolicyDecision(False, f"Unknown required fields: {unknown_required_fields}")

        return PolicyDecision(True, "Allowed")
```

- [ ] **Step 4: Run policy tests**

Run:

```bash
python -m pytest tests/test_policy/test_application_policy.py -v
```

Expected after implementation: PASS.

---

### Task 7: Template Writer Without LLM

**Files:**
- Create: `job_agent/writing/__init__.py`
- Create: `job_agent/writing/template_writer.py`
- Create: `tests/test_writing/__init__.py`
- Create: `tests/test_writing/test_template_writer.py`

- [ ] **Step 1: Write failing writer tests**

Create `tests/test_writing/test_template_writer.py`:

```python
from job_agent.database.models import Job
from job_agent.profile.user_profile import UserProfile
from job_agent.writing.template_writer import TemplateWriter


def _profile() -> UserProfile:
    return UserProfile(
        first_name="Test",
        last_name="User",
        full_name="Test User",
        email="test@example.com",
        phone="+92-300-1234567",
        location="Lahore, Pakistan",
        linkedin_url="https://linkedin.com/in/test",
        current_title="DevOps Engineer",
        current_company="Example",
        years_of_experience=3,
        summary="DevOps engineer.",
        cover_letter="Dear {company}, I am interested in {title}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=False,
        notice_period="Immediate",
    )


def test_cover_letter_uses_job_context_and_skills():
    writer = TemplateWriter()
    job = Job(platform="linkedin", title="DevOps Engineer", company="Acme", job_url="https://example.com")

    text = writer.cover_letter(_profile(), job, ["docker", "kubernetes", "terraform"])

    assert "Acme" in text
    assert "DevOps Engineer" in text
    assert "docker, kubernetes, terraform" in text
    assert "Lahore" in text


def test_employer_email_has_subject_and_body():
    writer = TemplateWriter()
    job = Job(platform="indeed", title="Cloud Engineer", company="CloudCo", job_url="https://example.com")

    email = writer.employer_email(_profile(), job, ["aws", "linux"])

    assert email.subject == "Application for Cloud Engineer - Test User"
    assert "CloudCo" in email.body
    assert "aws, linux" in email.body
    assert "https://linkedin.com/in/test" in email.body
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_writing/test_template_writer.py -v
```

Expected before implementation: FAIL with import errors.

- [ ] **Step 3: Implement template writer**

Create empty `job_agent/writing/__init__.py`.

Create `job_agent/writing/template_writer.py`:

```python
"""Local deterministic application text generation."""

from __future__ import annotations

from dataclasses import dataclass

from job_agent.database.models import Job
from job_agent.profile.user_profile import UserProfile


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body: str


class TemplateWriter:
    """Generates professional text from local templates, without any LLM."""

    def cover_letter(
        self,
        profile: UserProfile,
        job: Job,
        matched_skills: list[str],
    ) -> str:
        skills = self._skills_text(matched_skills)
        company = job.company or "your company"
        title = job.title or "the role"
        return (
            f"Dear Hiring Team,\n\n"
            f"I am applying for the {title} role at {company}. My background matches "
            f"your requirements in {skills}, and I have hands-on experience supporting "
            f"cloud infrastructure, automation, CI/CD pipelines, and production operations.\n\n"
            f"I am based in Lahore and would welcome the opportunity to contribute to "
            f"your engineering team.\n\n"
            f"Regards,\n"
            f"{profile.full_name}"
        )

    def employer_email(
        self,
        profile: UserProfile,
        job: Job,
        matched_skills: list[str],
    ) -> GeneratedEmail:
        title = job.title or "the role"
        company = job.company or "your company"
        skills = self._skills_text(matched_skills)
        subject = f"Application for {title} - {profile.full_name}"
        body = (
            f"Dear Hiring Team,\n\n"
            f"I recently applied for the {title} role at {company}. My experience aligns "
            f"with the role, especially around {skills}.\n\n"
            f"I am based in Lahore and available to discuss how I can contribute to your "
            f"engineering team. You can review my profile here: {profile.linkedin_url}\n\n"
            f"Regards,\n"
            f"{profile.full_name}\n"
            f"{profile.phone}\n"
            f"{profile.email}"
        )
        return GeneratedEmail(subject=subject, body=body)

    @staticmethod
    def _skills_text(matched_skills: list[str]) -> str:
        clean = [skill.strip() for skill in matched_skills if skill.strip()]
        return ", ".join(clean[:6]) if clean else "DevOps engineering and automation"
```

- [ ] **Step 4: Run writer tests**

Run:

```bash
python -m pytest tests/test_writing/test_template_writer.py -v
```

Expected after implementation: PASS.

---

### Task 8: Email Extraction And Outreach

**Files:**
- Create: `job_agent/outreach/__init__.py`
- Create: `job_agent/outreach/email_extractor.py`
- Create: `job_agent/outreach/email_outreach.py`
- Create: `tests/test_outreach/__init__.py`
- Create: `tests/test_outreach/test_email_extractor.py`

- [ ] **Step 1: Write failing email extractor tests**

Create `tests/test_outreach/test_email_extractor.py`:

```python
from job_agent.outreach.email_extractor import EmailExtractor


def test_extracts_visible_employer_emails():
    extractor = EmailExtractor()

    emails = extractor.extract("Apply by sending your CV to careers@example.com or hr@example.com")

    assert emails == ["careers@example.com", "hr@example.com"]


def test_filters_unhelpful_addresses():
    extractor = EmailExtractor()

    emails = extractor.extract("Contact privacy@example.com, noreply@example.com, recruitment@example.com")

    assert emails == ["recruitment@example.com"]


def test_prefers_recruiting_addresses_first():
    extractor = EmailExtractor()

    emails = extractor.extract("ali@example.com careers@example.com jobs@example.com")

    assert emails[:2] == ["careers@example.com", "jobs@example.com"]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_outreach/test_email_extractor.py -v
```

Expected before implementation: FAIL with import errors.

- [ ] **Step 3: Implement email extractor**

Create empty `job_agent/outreach/__init__.py`.

Create `job_agent/outreach/email_extractor.py`:

```python
"""Extract visible employer emails from job text."""

from __future__ import annotations

import re


class EmailExtractor:
    """Finds visible email addresses and filters unhelpful/system addresses."""

    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    BLOCKED_PREFIXES = ("privacy", "legal", "support", "noreply", "no-reply", "donotreply")
    PREFERRED_PREFIXES = ("careers", "career", "hr", "recruitment", "recruiting", "jobs", "talent")

    def extract(self, text: str) -> list[str]:
        found = []
        for match in self.EMAIL_RE.findall(text or ""):
            email = match.lower().strip(".,;:)")
            local = email.split("@", 1)[0]
            if local.startswith(self.BLOCKED_PREFIXES):
                continue
            found.append(email)

        unique = sorted(set(found), key=self._sort_key)
        return unique

    def _sort_key(self, email: str) -> tuple[int, str]:
        local = email.split("@", 1)[0]
        preferred = 0 if local.startswith(self.PREFERRED_PREFIXES) else 1
        return (preferred, email)
```

- [ ] **Step 4: Implement email outreach**

Create `job_agent/outreach/email_outreach.py`:

```python
"""Optional paced employer outreach."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_agent.config import Settings
    from job_agent.database.models import Job
    from job_agent.database.repository import ApplicationRepository
    from job_agent.notifications.email_client import EmailClient
    from job_agent.writing.template_writer import GeneratedEmail

logger = logging.getLogger("job_agent.outreach.email_outreach")


class EmailOutreach:
    """Sends employer emails only when enabled, capped, and not duplicated."""

    def __init__(
        self,
        repository: ApplicationRepository,
        email_client: EmailClient,
        settings: Settings,
    ):
        self.repository = repository
        self.email_client = email_client
        self.settings = settings

    async def send_if_allowed(
        self,
        job: Job,
        recipient: str,
        generated: GeneratedEmail,
    ) -> bool:
        if not self.settings.auto_send_employer_emails:
            self.repository.save_outreach(
                job_id=job.id or 0,
                recipient=recipient,
                subject=generated.subject,
                body=generated.body,
                status="Skipped",
                failure_reason="Employer outreach disabled",
            )
            return False

        if self.repository.get_today_outreach_count() >= self.settings.max_employer_emails_per_day:
            self.repository.save_outreach(
                job_id=job.id or 0,
                recipient=recipient,
                subject=generated.subject,
                body=generated.body,
                status="Skipped",
                failure_reason="Daily employer email limit reached",
            )
            return False

        if self.repository.was_email_contacted(job.id or 0, recipient):
            return False

        delay = random.uniform(
            self.settings.min_email_delay_minutes * 60,
            self.settings.max_email_delay_minutes * 60,
        )
        logger.info("Waiting %.0fs before employer outreach email", delay)
        await asyncio.sleep(delay)

        html_body = generated.body.replace("\n", "<br>")
        sent = self.email_client.send(recipient, generated.subject, html_body)
        self.repository.save_outreach(
            job_id=job.id or 0,
            recipient=recipient,
            subject=generated.subject,
            body=generated.body,
            status="Sent" if sent else "Failed",
            failure_reason=None if sent else "SMTP send failed",
        )
        return sent
```

- [ ] **Step 5: Run outreach tests**

Run:

```bash
python -m pytest tests/test_outreach/test_email_extractor.py -v
```

Expected after implementation: PASS.

---

### Task 9: Excel Reporter

**Files:**
- Create: `job_agent/reports/__init__.py`
- Create: `job_agent/reports/excel_reporter.py`
- Create: `tests/test_reports/__init__.py`
- Create: `tests/test_reports/test_excel_reporter.py`

- [ ] **Step 1: Write failing report test**

Create `tests/test_reports/test_excel_reporter.py`:

```python
from pathlib import Path

from openpyxl import load_workbook

from job_agent.reports.excel_reporter import ExcelReporter


def test_excel_reporter_writes_expected_columns(tmp_path: Path):
    rows = [
        {
            "applied_at": "2026-05-04T09:00:00",
            "platform": "linkedin",
            "title": "DevOps Engineer",
            "company": "Acme",
            "recipient": "careers@example.com",
            "location": "Lahore",
            "job_url": "https://example.com/job",
            "is_easy_apply": 1,
            "is_external": 0,
            "match_score": 82,
            "matched_keywords": '["docker", "kubernetes"]',
            "subject": "Application for DevOps Engineer - Test User",
            "body": "Dear Hiring Team",
            "application_status": "Applied",
            "outreach_status": "Sent",
            "application_reason": None,
            "outreach_reason": None,
        }
    ]
    reporter = ExcelReporter(tmp_path)

    path = reporter.write_daily(rows, date_slug="2026-05-04")

    assert path.exists()
    workbook = load_workbook(path)
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    assert "Job Title" in headers
    assert "Employer Email" in headers
    assert sheet["C2"].value == "DevOps Engineer"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest tests/test_reports/test_excel_reporter.py -v
```

Expected before implementation: FAIL with import error.

- [ ] **Step 3: Implement Excel reporter**

Create empty `job_agent/reports/__init__.py`.

Create `job_agent/reports/excel_reporter.py`:

```python
"""XLSX reporting for daily application runs."""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


class ExcelReporter:
    """Writes daily application and outreach records to an Excel workbook."""

    HEADERS = [
        "Date/Time",
        "Platform",
        "Job Title",
        "Company",
        "Employer Email",
        "Location",
        "Job URL",
        "Apply Type",
        "Match Score",
        "Matched Skills",
        "Generated Subject",
        "Generated Text Preview",
        "Application Status",
        "Outreach Status",
        "Failure/Manual Reason",
    ]

    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir

    def write_daily(self, rows: list[dict], date_slug: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"applications_{date_slug}.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Applications"
        sheet.append(self.HEADERS)

        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for row in rows:
            sheet.append(self._row_values(row))

        for idx, _ in enumerate(self.HEADERS, start=1):
            sheet.column_dimensions[get_column_letter(idx)].width = 22

        workbook.save(path)
        return path

    def _row_values(self, row: dict) -> list:
        body = row.get("body") or ""
        return [
            row.get("applied_at") or row.get("sent_at") or "",
            row.get("platform") or "",
            row.get("title") or "",
            row.get("company") or "",
            row.get("recipient") or "",
            row.get("location") or "",
            row.get("job_url") or "",
            self._apply_type(row),
            row.get("match_score") or "",
            self._keywords(row.get("matched_keywords")),
            row.get("subject") or "",
            body[:240],
            row.get("application_status") or "",
            row.get("outreach_status") or "",
            row.get("application_reason") or row.get("outreach_reason") or row.get("safety_reason") or "",
        ]

    @staticmethod
    def _apply_type(row: dict) -> str:
        if row.get("is_easy_apply"):
            return "Easy Apply"
        if row.get("is_external"):
            return "External"
        return ""

    @staticmethod
    def _keywords(value) -> str:
        if not value:
            return ""
        if isinstance(value, list):
            return ", ".join(value)
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return ", ".join(str(item) for item in parsed)
        except Exception:
            return str(value)
        return str(value)
```

- [ ] **Step 4: Run report tests**

Run:

```bash
python -m pytest tests/test_reports/test_excel_reporter.py -v
```

Expected after implementation: PASS.

---

### Task 10: Form Filling Result Safety

**Files:**
- Modify: `job_agent/forms/filler.py`
- Test: `tests/test_forms/test_field_mapping.py`

- [ ] **Step 1: Add FormFillResult dataclass**

In `job_agent/forms/filler.py`, add near imports:

```python
from dataclasses import dataclass, field
```

Add below imports:

```python
@dataclass
class FormFillResult:
    filled_count: int = 0
    unfilled: list[str] = field(default_factory=list)
    unknown_required_count: int = 0
```

- [ ] **Step 2: Change fill_form return type**

Change:

```python
    ) -> list[str]:
```

to:

```python
    ) -> FormFillResult:
```

Replace the final lines of `fill_form()` with:

```python
        filled_count = len(fields) - len(unfilled)
        required_unfilled = [
            (field.label_text or field.name_attr or field.selector)
            for field in fields
            if field.is_required and (field.label_text or field.name_attr or field.selector) in unfilled
        ]
        logger.info("Filled %d/%d fields", filled_count, len(fields))
        return FormFillResult(
            filled_count=filled_count,
            unfilled=unfilled,
            unknown_required_count=len(required_unfilled),
        )
```

- [ ] **Step 3: Preserve compatibility in platform code later**

No tests are added in this task because current field mapping tests do not call `fill_form()`. Platform integration updates in Task 11 must use `fill_result.unfilled` and `fill_result.unknown_required_count`.

- [ ] **Step 4: Run existing form tests**

Run:

```bash
python -m pytest tests/test_forms/test_field_mapping.py -v
```

Expected after implementation: PASS.

---

### Task 11: Platform Integration, Matching, Pacing, And Dry Run

**Files:**
- Modify: `job_agent/platforms/base.py`
- Modify: `job_agent/platforms/linkedin/applier.py`
- Modify: `job_agent/platforms/indeed/applier.py`
- Modify: `job_agent/main.py`

- [ ] **Step 1: Add platform constructor dependencies**

In `job_agent/platforms/base.py` TYPE_CHECKING imports, include:

```python
    from job_agent.matching.job_matcher import JobMatcher
    from job_agent.matching.location_filter import LocationFilter
    from job_agent.outreach.email_extractor import EmailExtractor
    from job_agent.outreach.email_outreach import EmailOutreach
    from job_agent.policy.application_policy import ApplicationPolicy
    from job_agent.writing.template_writer import TemplateWriter
```

Extend `BasePlatform.__init__()` parameters:

```python
        application_policy: ApplicationPolicy,
        job_matcher: JobMatcher,
        location_filter: LocationFilter,
        template_writer: TemplateWriter,
        email_extractor: EmailExtractor,
        email_outreach: EmailOutreach | None,
        resume_text: str,
```

Store them:

```python
        self.application_policy = application_policy
        self.job_matcher = job_matcher
        self.location_filter = location_filter
        self.template_writer = template_writer
        self.email_extractor = email_extractor
        self.email_outreach = email_outreach
        self.resume_text = resume_text
```

- [ ] **Step 2: Add abstract job detail method**

In `BasePlatform`, add:

```python
    @abstractmethod
    async def get_job_description(self, job: Job) -> str:
        """Load and return visible job detail text for matching."""
        ...
```

Implement in `LinkedInPlatform`:

```python
    async def get_job_description(self, job: Job) -> str:
        page = await self.session.get_page()
        await page.goto(job.job_url, wait_until="domcontentloaded")
        await self.humanizer.random_delay()
        try:
            return await page.inner_text("body")
        except Exception:
            return ""
```

Implement the same method in `IndeedPlatform`.

- [ ] **Step 3: Add matching and policy before apply**

In `BasePlatform.run()`, after `job.id = job_id` and before the duplicate check/apply call, add:

```python
            if not self.location_filter.is_allowed(job.location):
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=f"Location rejected: {job.location or 'unknown'}",
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            job_description = await self.get_job_description(job)
            match_result = self.job_matcher.score(
                job=job,
                query=SearchQuery(title=job.title, location=job.location or ""),
                profile=self.profile,
                resume_text=self.resume_text,
                job_description=job_description,
            )
            self.repository.update_job_match(
                job_id=job_id,
                job_description=job_description[:5000],
                match_score=match_result.score,
                matched_keywords=match_result.matched_keywords,
                location_allowed=True,
                safety_reason=match_result.reason,
            )

            decision = self.application_policy.evaluate(
                job=job,
                match_result=match_result,
                unknown_required_fields=0,
            )
            if not decision.allowed:
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=decision.status_reason,
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue

            if self.settings.dry_run:
                app = AppModel(
                    job_id=job_id,
                    status=ApplicationStatus.SKIPPED,
                    failure_reason=f"Dry run: would apply. Score={match_result.score}",
                )
                self.repository.save_application(app)
                stats["skipped"] += 1
                continue
```

- [ ] **Step 4: Add pacing after successful applications**

In `BasePlatform.run()`, after an application is saved and `stats["applied"]` increments, add:

```python
                    if stats["applied"] % max(self.settings.long_break_every_applications, 1) == 0:
                        pause = self.settings.long_break_minutes * 60
                    else:
                        pause = random.uniform(
                            self.settings.min_application_delay_minutes * 60,
                            self.settings.max_application_delay_minutes * 60,
                        )
                    self.logger.info("Application pacing pause: %.0fs", pause)
                    await asyncio.sleep(pause)
```

Add `import asyncio` at the top of `base.py`.

- [ ] **Step 5: Use generated cover letter text in form filling**

In `FormFiller._fill_field()`, replace cover letter handling:

```python
        if profile_key == "cover_letter" and job:
            value = self.profile.get_cover_letter_for(
                company=job.company or "your company",
                title=job.title or "the position",
            )
```

with:

```python
        if profile_key == "cover_letter" and job:
            value = self.profile.get_cover_letter_for(
                company=job.company or "your company",
                title=job.title or "the position",
            )
```

Then in a follow-up refactor, inject `TemplateWriter` into `FormFiller` only if needed. For this implementation, keep `UserProfile.get_cover_letter_for()` and update the profile cover letter template in docs to a professional local template. This avoids a broad constructor change.

- [ ] **Step 6: Update platform fill result use**

In `job_agent/platforms/linkedin/applier.py` and `job_agent/platforms/indeed/applier.py`, replace patterns like:

```python
                unfilled = await self.form_filler.fill_form(
                    self.page, fields, job
                )
                if unfilled:
                    logger.debug("Unfilled fields: %s", unfilled)
```

with:

```python
                fill_result = await self.form_filler.fill_form(
                    self.page, fields, job
                )
                if fill_result.unfilled:
                    logger.debug("Unfilled fields: %s", fill_result.unfilled)
                if fill_result.unknown_required_count > 0:
                    raise FormFillingError(
                        platform="linkedin",
                        field_name="required fields",
                        reason=f"Unknown required fields: {fill_result.unknown_required_count}",
                    )
```

For Indeed, use `platform="indeed"` and import `FormFillingError`.

- [ ] **Step 7: Wire services in main**

In `job_agent/main.py`, import:

```python
from job_agent.matching.job_matcher import JobMatcher
from job_agent.matching.location_filter import LocationFilter
from job_agent.matching.resume_parser import ResumeParser, ResumeParseError
from job_agent.outreach.email_extractor import EmailExtractor
from job_agent.outreach.email_outreach import EmailOutreach
from job_agent.policy.application_policy import ApplicationPolicy
from job_agent.reports.excel_reporter import ExcelReporter
from job_agent.writing.template_writer import TemplateWriter
```

In `async_main()`, after profile load, add:

```python
    try:
        resume_text = ResumeParser().parse(settings.resume_path)
    except ResumeParseError as e:
        logger.error("Failed to load resume for matching: %s", e)
        sys.exit(1)
```

Extend `run_platform()` signature with `resume_text: str`.

Inside `run_platform()`, after `rate_limiter`, create:

```python
        application_policy = ApplicationPolicy(
            repository=repository,
            global_daily_limit=settings.global_daily_application_limit,
            max_unknown_required_fields=settings.max_unknown_required_fields,
        )
        job_matcher = JobMatcher(
            min_score=settings.min_match_score,
            excluded_keywords=settings.match_excluded_keywords,
            required_skills=settings.match_required_skills,
        )
        location_filter = LocationFilter(
            settings.target_locations,
            strict=settings.strict_location_filter,
        )
        template_writer = TemplateWriter()
        email_extractor = EmailExtractor()
        email_outreach = EmailOutreach(repository, reporter.email_client, settings)
```

Pass all new dependencies into `PlatformClass(...)`.

When calling `run_platform()`, pass `resume_text=resume_text`.

- [ ] **Step 8: Export Excel report in main**

After `reporter.send_daily_summary()`, add:

```python
    if settings.export_excel_report:
        date_slug = datetime.now().strftime("%Y-%m-%d")
        export_rows = repository.get_daily_export_rows()
        report_path = ExcelReporter(settings.reports_dir).write_daily(export_rows, date_slug)
        logger.info("Excel report exported: %s", report_path)
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
python -m pytest tests/test_config.py tests/test_database/test_repository.py tests/test_matching tests/test_policy tests/test_writing tests/test_outreach tests/test_reports -v
```

Expected after implementation: PASS.

---

### Task 12: Scheduler Path Fixes And Documentation

**Files:**
- Modify: `scripts/run_agent.bat`
- Modify: `scripts/setup_scheduler.ps1`
- Modify: `README.md`
- Modify: `details.md`

- [ ] **Step 1: Fix `scripts/run_agent.bat`**

Replace the hardcoded path script with:

```bat
@echo off
REM ============================================
REM AI Job Application Agent - Daily Launcher
REM ============================================

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python -m job_agent.main
set EXIT_CODE=%ERRORLEVEL%

if defined VIRTUAL_ENV (
    deactivate
)

exit /b %EXIT_CODE%
```

- [ ] **Step 2: Fix `scripts/setup_scheduler.ps1` paths**

Replace path assignments with:

```powershell
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$BatPath = Join-Path $ProjectRoot "scripts\run_agent.bat"
$WorkingDir = $ProjectRoot
$LogPath = Join-Path $ProjectRoot "data\logs\scheduler.log"
```

Keep the existing task creation logic.

- [ ] **Step 3: Update README**

Add a section:

```markdown
## Safe Auto-Apply Mode

The agent now applies only after these gates pass:

- Lahore-only location filter
- Resume/job keyword match
- Global daily cap of 30 successful applications
- Duplicate application check
- CAPTCHA/security check
- Required-field confidence check

The matching and writing engine is local and deterministic. It does not use an LLM.

Employer outreach is disabled by default. To enable it, set:

```env
AUTO_SEND_EMPLOYER_EMAILS=true
MAX_EMPLOYER_EMAILS_PER_DAY=10
```

The agent only sends employer emails when a real visible email address is found in the job text or application page.
```

- [ ] **Step 4: Update details.md**

Append:

```markdown
## Safe Auto-Apply Enhancement

The enhancement plan adds Lahore-only filtering, local resume parsing, deterministic keyword matching, a global 30/day application cap, local template-based writing without an LLM, optional paced employer emails, and Excel reporting under `data/reports/`.
```

- [ ] **Step 5: Run text checks**

Run:

```bash
rg -n "HamzaAkhtar|C:\\Users\\HamzaAkhtar" scripts README.md details.md
```

Expected after implementation: no matches.

---

### Task 13: Final Verification

**Files:**
- All modified files.

- [ ] **Step 1: Install missing dev/test dependencies if needed**

Run:

```bash
python -m pip install -r requirements.txt pytest pytest-asyncio
```

Expected: dependencies install successfully. If network restrictions block installation, request approval for networked dependency installation and rerun.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Run import smoke check**

Run:

```bash
python -c "from job_agent.main import main; from job_agent.matching.job_matcher import JobMatcher; from job_agent.reports.excel_reporter import ExcelReporter; print('imports ok')"
```

Expected:

```text
imports ok
```

- [ ] **Step 4: Run dry-run configuration check**

Set `DRY_RUN=true` in `.env`, then run:

```bash
python -m job_agent.main
```

Expected:

- Loads settings.
- Loads profile.
- Parses resume.
- Opens browser only if platform sessions are available.
- Does not click final submit buttons.
- Does not send employer emails.
- Writes logs and an Excel report if job data is available.

- [ ] **Step 5: Record remaining operational requirements**

Confirm these before real auto-apply:

- Resume exists at `RESUME_PATH`.
- LinkedIn/Indeed sessions are saved via `scripts/manual_login.py`.
- `DRY_RUN=false` only after a successful dry run.
- `AUTO_SEND_EMPLOYER_EMAILS=true` only after reviewing generated XLSX output.
- Daily limits and delays are acceptable.

---

## Self-Review Notes

- Spec coverage: The plan covers global cap, Lahore filtering, local resume parsing, local deterministic matching, local template writing, Excel reporting, optional paced employer email, scheduler path fixes, tests, and dry-run verification.
- Ambiguity resolved: Default employer outreach is disabled and only enabled by `.env`; outreach only uses visible emails and never guesses addresses.
- Scope decision: The plan keeps Playwright for actual apply actions because official LinkedIn/Indeed apply APIs are restricted partner integrations.
