from job_agent.database.models import Job
from job_agent.utils.job_identity import job_dedup_key


def test_job_dedup_key_uses_indeed_jk():
    job_a = Job(
        platform="indeed",
        title="Developer",
        job_url="https://pk.indeed.com/rc/clk?jk=abc123&bb=tracking",
        external_id="abc123",
    )
    job_b = Job(
        platform="indeed",
        title="Developer",
        job_url="https://pk.indeed.com/viewjob?jk=abc123",
        external_id="abc123",
    )
    assert job_dedup_key(job_a) == job_dedup_key(job_b)
