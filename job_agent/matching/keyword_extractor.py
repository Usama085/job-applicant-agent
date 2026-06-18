"""Deterministic keyword extraction for resume and job matching."""

from __future__ import annotations

import re


class KeywordExtractor:
    """Extracts a stable set of known technical and role keywords."""

    DEFAULT_KEYWORDS = {
        "ansible",
        "aws",
        "azure",
        "bash",
        "ci/cd",
        "cloud",
        "devops",
        "docker",
        "gcp",
        "git",
        "github actions",
        "gitlab",
        "grafana",
        "jenkins",
        "kubernetes",
        "linux",
        "monitoring",
        "nginx",
        "prometheus",
        "python",
        "scripting",
        "terraform",
        "windows server",
    }

    def __init__(self, extra_keywords: list[str] | None = None):
        self.keywords = set(self.DEFAULT_KEYWORDS)
        if extra_keywords:
            self.keywords.update(k.strip().lower() for k in extra_keywords if k.strip())

    def extract(self, text: str) -> list[str]:
        normalized = self.normalize(text)
        found = []
        for keyword in self.keywords:
            pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
            if re.search(pattern, normalized):
                found.append(keyword)
        return sorted(set(found))

    @staticmethod
    def normalize(text: str) -> str:
        lowered = text.lower()
        lowered = lowered.replace("cicd", "ci/cd")
        lowered = re.sub(r"[\s_]+", " ", lowered)
        return lowered
