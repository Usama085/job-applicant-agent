"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from job_agent.database.repository import ApplicationRepository
from job_agent.profile.user_profile import UserProfile


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def repository(tmp_db: Path) -> ApplicationRepository:
    """Create a repository with a fresh test database."""
    repo = ApplicationRepository(tmp_db)
    repo.connect()
    yield repo
    repo.close()


@pytest.fixture
def sample_profile() -> UserProfile:
    """Create a sample user profile for testing."""
    return UserProfile(
        first_name="Test",
        last_name="User",
        full_name="Test User",
        email="test@example.com",
        phone="+92-300-1234567",
        location="Lahore, Pakistan",
        linkedin_url="https://www.linkedin.com/in/testuser",
        current_title="DevOps Engineer",
        current_company="Test Corp",
        years_of_experience=3,
        summary="Test summary",
        cover_letter="Dear Hiring Manager, I am interested in {title} at {company}.",
        salary_expectation="Negotiable",
        work_authorization="Authorized",
        visa_sponsorship_required=False,
        availability_date="Immediate",
        willing_to_relocate=True,
        notice_period="2 weeks",
        references=[],
    )
