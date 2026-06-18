from pathlib import Path

import pytest

from job_agent.matching.resume_parser import ResumeParser, ResumeParseError


def test_parse_txt_resume(tmp_path: Path):
    resume = tmp_path / "resume.txt"
    resume.write_text("DevOps Engineer\nPython Docker Kubernetes Lahore", encoding="utf-8")

    parser = ResumeParser()
    text = parser.parse(resume)

    assert "DevOps Engineer" in text
    assert "Kubernetes" in text


def test_missing_resume_raises(tmp_path: Path):
    parser = ResumeParser()

    with pytest.raises(ResumeParseError, match="Resume file not found"):
        parser.parse(tmp_path / "missing.pdf")


def test_unsupported_resume_type_raises(tmp_path: Path):
    resume = tmp_path / "resume.rtf"
    resume.write_text("content", encoding="utf-8")
    parser = ResumeParser()

    with pytest.raises(ResumeParseError, match="Unsupported resume format"):
        parser.parse(resume)
