"""Tests for heuristic field mapping rules."""

from job_agent.forms.field_mapping import FieldMapping
from job_agent.profile.user_profile import UserProfile


def _make_profile() -> UserProfile:
    return UserProfile(
        first_name="Hamza",
        last_name="Akhtar",
        full_name="Hamza Akhtar",
        email="hamza@example.com",
        phone="+92-300-1234567",
        location="Lahore, Pakistan",
        linkedin_url="https://linkedin.com/in/hamza",
        current_title="DevOps Engineer",
        current_company="TestCo",
        years_of_experience=3,
        summary="Test summary",
        cover_letter="Dear {company}, interested in {title}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized to work",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=True,
        notice_period="2 weeks",
    )


def test_first_name_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("first name", profile)
    assert key == "first_name"
    assert value == "Hamza"


def test_last_name_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("last name", profile)
    assert key == "last_name"
    assert value == "Akhtar"


def test_email_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("email address", profile)
    assert key == "email"
    assert value == "hamza@example.com"


def test_phone_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("phone number", profile)
    assert key == "phone"
    assert value == "+92-300-1234567"


def test_linkedin_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("linkedin url", profile)
    assert key == "linkedin_url"
    assert value == "https://linkedin.com/in/hamza"


def test_experience_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("years of experience", profile)
    assert key == "years_of_experience"
    assert value == "3"


def test_salary_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("expected salary range", profile)
    assert key == "salary_expectation"
    assert value == "Negotiable"


def test_visa_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("do you require visa sponsorship", profile)
    assert key == "visa_sponsorship_required"
    assert value == "No"  # False -> "No"


def test_relocate_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("willing to relocate", profile)
    assert key == "willing_to_relocate"
    assert value == "Yes"  # True -> "Yes"


def test_no_match():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("favorite color", profile)
    assert key is None
    assert value is None


def test_work_authorization():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("are you legally authorized to work", profile)
    assert key == "work_authorization"
    assert value == "Authorized to work"


def test_notice_period():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("current notice period", profile)
    assert key == "notice_period"
    assert value == "2 weeks"


def test_availability_mapping():
    mapping = FieldMapping()
    profile = _make_profile()
    key, value = mapping.find_match("when can you start", profile)
    assert key == "availability_date"
    assert value == "Immediate"
