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
