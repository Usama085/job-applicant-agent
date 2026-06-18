"""Heuristic rules engine for mapping form fields to user profile data."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from job_agent.profile.user_profile import UserProfile

logger = logging.getLogger("job_agent.forms.field_mapping")


@dataclass
class MappingRule:
    """A single mapping rule: regex pattern -> profile attribute."""

    pattern: re.Pattern[str]
    profile_key: str
    priority: int  # Higher = preferred when multiple rules match


class FieldMapping:
    """Maps form field identifiers to user profile values using regex heuristics."""

    def __init__(self) -> None:
        self.rules: list[MappingRule] = self._build_default_rules()

    def find_match(
        self, identifiers: str, profile: UserProfile
    ) -> tuple[str | None, str | None]:
        """Try all rules against the field identifiers.

        Args:
            identifiers: Combined lowercase string of label, name, id, placeholder.
            profile: The user profile to extract values from.

        Returns:
            Tuple of (profile_key, value) for the highest-priority match,
            or (None, None) if no rule matches.
        """
        best_match: tuple[str | None, str | None] = (None, None)
        best_priority = -1

        for rule in self.rules:
            if rule.pattern.search(identifiers) and rule.priority > best_priority:
                value = self._get_profile_value(profile, rule.profile_key)
                if value is not None:
                    best_match = (rule.profile_key, value)
                    best_priority = rule.priority

        return best_match

    @staticmethod
    def _get_profile_value(profile: UserProfile, key: str) -> str | None:
        """Get a string value from the profile by key."""
        val = getattr(profile, key, None)
        if val is None:
            return None
        if isinstance(val, bool):
            return "Yes" if val else "No"
        if isinstance(val, int):
            return str(val)
        return str(val) if val else None

    @staticmethod
    def _build_default_rules() -> list[MappingRule]:
        """Build the default set of regex mapping rules."""
        # Use re.IGNORECASE for all patterns
        def p(pattern: str) -> re.Pattern[str]:
            return re.compile(pattern, re.IGNORECASE)

        return [
            # --- Name fields (high priority) ---
            MappingRule(p(r"first[\s_.-]?name"), "first_name", 10),
            MappingRule(p(r"last[\s_.-]?name|surname|family[\s_.-]?name"), "last_name", 10),
            MappingRule(p(r"full[\s_.-]?name|your[\s_.-]?name|^name$|applicant.?name"), "full_name", 9),
            # --- Contact ---
            MappingRule(p(r"e[\s_.-]?mail|email.?address"), "email", 10),
            MappingRule(p(r"phone|mobile|cell|telephone|contact.?number"), "phone", 10),
            # --- Location ---
            MappingRule(p(r"city|location|where.?do.?you.?live|current.?location"), "location", 8),
            # --- LinkedIn ---
            MappingRule(p(r"linkedin|linked[\s_.-]?in"), "linkedin_url", 9),
            # --- Professional ---
            MappingRule(
                p(r"experience|years?.?of.?experience|how.?many.?years|yoe"),
                "years_of_experience",
                8,
            ),
            MappingRule(
                p(r"current[\s_.-]?title|job[\s_.-]?title|position|role|designation"),
                "current_title",
                7,
            ),
            MappingRule(
                p(r"current[\s_.-]?company|employer|organization|where.?do.?you.?work"),
                "current_company",
                7,
            ),
            MappingRule(p(r"summary|about.?you|bio|introduction|profile"), "summary", 5),
            # --- Application specific ---
            MappingRule(p(r"cover[\s_.-]?letter|motivation|why.?this"), "cover_letter", 8),
            MappingRule(
                p(r"salary|compensation|pay|expected.?ctc|desired.?salary|package"),
                "salary_expectation",
                7,
            ),
            MappingRule(
                p(r"work[\s_.-]?auth|legally|eligible.?to.?work|right.?to.?work|authorized"),
                "work_authorization",
                9,
            ),
            MappingRule(
                p(r"visa|sponsor|immigration|work.?permit"),
                "visa_sponsorship_required",
                9,
            ),
            MappingRule(
                p(r"start[\s_.-]?date|avail|when.?can.?you.?(join|start)|earliest|date.?of.?joining"),
                "availability_date",
                7,
            ),
            MappingRule(p(r"notice[\s_.-]?period|serving.?notice"), "notice_period", 7),
            MappingRule(
                p(r"relocat|willing.?to.?move|open.?to.?relocation"),
                "willing_to_relocate",
                6,
            ),
        ]
