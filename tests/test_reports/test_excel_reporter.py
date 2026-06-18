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
