"""Tests for Indeed job URL normalization."""

from job_agent.platforms.indeed.urls import canonical_job_url, extract_job_key


def test_extract_job_key_from_tracking_url():
    url = (
        "https://pk.indeed.com/rc/clk?jk=abc123def&bb=tracking"
        "&cmp=Hiring-Talent&ti=Full+Stack+Developer"
    )
    assert extract_job_key(url) == "abc123def"


def test_canonical_job_url_from_tracking_link():
    tracking = "https://pk.indeed.com/rc/clk?jk=abc123def&bb=tracking"
    assert canonical_job_url(tracking) == "https://pk.indeed.com/viewjob?jk=abc123def"


def test_canonical_job_url_uses_external_id():
    tracking = "https://pk.indeed.com/rc/clk?jk=old"
    assert canonical_job_url(tracking, "newkey456") == "https://pk.indeed.com/viewjob?jk=newkey456"
