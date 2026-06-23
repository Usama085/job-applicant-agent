"""Indeed job URL helpers."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from job_agent.platforms.indeed import constants


def extract_job_key(url: str, external_id: str | None = None) -> str | None:
    """Extract Indeed job key (jk) from a URL or external id."""
    if external_id:
        return external_id

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    jk_values = query.get("jk") or query.get("vjk")
    if jk_values:
        return jk_values[0]

    return None


def canonical_job_url(url: str, external_id: str | None = None) -> str:
    """Return a stable viewjob URL instead of /rc/clk tracking links."""
    jk = extract_job_key(url, external_id)
    if jk:
        base = constants.HOME_URL.rstrip("/")
        return f"{base}/viewjob?jk={jk}"

    if "/viewjob" in url:
        return url

    return url
