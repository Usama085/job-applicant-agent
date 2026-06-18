"""Extract visible employer emails from job text."""

from __future__ import annotations

import re


class EmailExtractor:
    """Finds visible email addresses and filters unhelpful/system addresses."""

    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    BLOCKED_PREFIXES = ("privacy", "legal", "support", "noreply", "no-reply", "donotreply")
    PREFERRED_PREFIXES = ("careers", "career", "hr", "recruitment", "recruiting", "jobs", "talent")

    def extract(self, text: str) -> list[str]:
        found = []
        for match in self.EMAIL_RE.findall(text or ""):
            email = match.lower().strip(".,;:)")
            local = email.split("@", 1)[0]
            if local.startswith(self.BLOCKED_PREFIXES):
                continue
            found.append(email)

        return sorted(set(found), key=self._sort_key)

    def _sort_key(self, email: str) -> tuple[int, str]:
        local = email.split("@", 1)[0]
        preferred = 0 if local.startswith(self.PREFERRED_PREFIXES) else 1
        return (preferred, email)
