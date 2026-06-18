from dataclasses import dataclass

import pytest

from job_agent.database.models import Job
from job_agent.outreach.email_outreach import EmailOutreach
from job_agent.writing.template_writer import GeneratedEmail


@dataclass
class FakeSettings:
    auto_send_employer_emails: bool = False
    max_employer_emails_per_day: int = 10
    min_email_delay_minutes: int = 0
    max_email_delay_minutes: int = 0


class FakeRepository:
    def __init__(self):
        self.records = []
        self.count = 0
        self.contacted = False

    def save_outreach(self, **kwargs):
        self.records.append(kwargs)
        return len(self.records)

    def get_today_outreach_count(self):
        return self.count

    def was_email_contacted(self, job_id, recipient):
        return self.contacted


class FakeEmailClient:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, html_body):
        self.sent.append((to, subject, html_body))
        return True


@pytest.mark.asyncio
async def test_outreach_disabled_records_skipped():
    repo = FakeRepository()
    client = FakeEmailClient()
    outreach = EmailOutreach(repo, client, FakeSettings(auto_send_employer_emails=False))
    job = Job(id=1, platform="linkedin", title="DevOps", job_url="https://example.com")

    sent = await outreach.send_if_allowed(
        job,
        "careers@example.com",
        GeneratedEmail("Subject", "Body"),
    )

    assert sent is False
    assert client.sent == []
    assert repo.records[0]["status"] == "Skipped"
    assert repo.records[0]["failure_reason"] == "Employer outreach disabled"


@pytest.mark.asyncio
async def test_outreach_enabled_sends_and_records(monkeypatch):
    async def no_sleep(seconds):
        return None

    monkeypatch.setattr("job_agent.outreach.email_outreach.asyncio.sleep", no_sleep)
    repo = FakeRepository()
    client = FakeEmailClient()
    outreach = EmailOutreach(repo, client, FakeSettings(auto_send_employer_emails=True))
    job = Job(id=1, platform="linkedin", title="DevOps", job_url="https://example.com")

    sent = await outreach.send_if_allowed(
        job,
        "careers@example.com",
        GeneratedEmail("Subject", "Line 1\nLine 2"),
    )

    assert sent is True
    assert client.sent == [("careers@example.com", "Subject", "Line 1<br>Line 2")]
    assert repo.records[0]["status"] == "Sent"
