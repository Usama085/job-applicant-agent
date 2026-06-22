"""Load user profile from YAML configuration file."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from job_agent.profile.user_profile import Reference, UserProfile

logger = logging.getLogger("job_agent.profile.profile_loader")

DEFAULT_PROFILE_PATH = Path("config/profile.yaml")


def load_profile(path: Path | None = None) -> UserProfile:
    """Load and validate user profile from a YAML file."""
    profile_path = path or DEFAULT_PROFILE_PATH

    if not profile_path.exists():
        raise FileNotFoundError(
            f"Profile file not found: {profile_path}\n"
            "Create it from the template in config/profile.yaml"
        )

    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    personal = data.get("personal", {})
    professional = data.get("professional", {})
    defaults = data.get("application_defaults", {})
    education = data.get("education", {})
    refs_data = data.get("references", [])

    references = [
        Reference(
            name=r.get("name", ""),
            title=r.get("title", ""),
            company=r.get("company", ""),
            email=r.get("email", ""),
            phone=r.get("phone", ""),
        )
        for r in refs_data
    ]

    profile = UserProfile(
        first_name=personal.get("first_name", ""),
        last_name=personal.get("last_name", ""),
        full_name=personal.get("full_name", ""),
        email=personal.get("email", ""),
        phone=personal.get("phone", ""),
        location=personal.get("location", ""),
        linkedin_url=personal.get("linkedin_url", ""),
        street_address=personal.get("street_address", ""),
        postcode=personal.get("postcode", ""),
        country=personal.get("country", ""),
        current_title=professional.get("current_title", ""),
        current_company=professional.get("current_company", ""),
        years_of_experience=int(professional.get("years_of_experience", 0)),
        summary=professional.get("summary", ""),
        cover_letter=defaults.get("cover_letter", ""),
        salary_expectation=defaults.get("salary_expectation", "Negotiable"),
        work_authorization=defaults.get("work_authorization", ""),
        visa_sponsorship_required=bool(defaults.get("visa_sponsorship_required", False)),
        availability_date=defaults.get("availability_date", "Immediate"),
        willing_to_relocate=bool(defaults.get("willing_to_relocate", True)),
        notice_period=defaults.get("notice_period", ""),
        education_degree=education.get("degree", ""),
        graduation_year=int(education["graduation_year"])
        if education.get("graduation_year")
        else None,
        references=references,
    )

    # Validate required fields
    required = ["first_name", "last_name", "email", "phone"]
    missing = [f for f in required if not getattr(profile, f)]
    if missing:
        raise ValueError(f"Missing required profile fields: {', '.join(missing)}")

    logger.info("Profile loaded for: %s", profile.full_name)
    return profile
