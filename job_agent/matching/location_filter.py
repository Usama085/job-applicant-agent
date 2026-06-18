"""Location filtering for Lahore-only job targeting."""

from __future__ import annotations


class LocationFilter:
    """Allows jobs only when their visible location matches configured targets."""

    BLOCKED_TERMS = {"karachi", "islamabad", "rawalpindi", "faisalabad", "remote"}

    def __init__(self, allowed_locations: list[str], strict: bool = True):
        self.strict = strict
        self.allowed_locations = [
            self._normalize(location)
            for location in allowed_locations
            if location and location.strip()
        ]

    def is_allowed(self, location: str | None) -> bool:
        if not location or not location.strip():
            return not self.strict

        normalized = self._normalize(location)
        if any(term in normalized for term in self.BLOCKED_TERMS):
            return "lahore" in normalized and "remote" not in normalized

        return any(
            allowed in normalized or normalized in allowed
            for allowed in self.allowed_locations
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.lower().replace(",", " ").split())
