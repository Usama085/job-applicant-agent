"""Local resume text extraction for PDF, DOCX, and TXT files."""

from __future__ import annotations

from pathlib import Path


class ResumeParseError(Exception):
    """Raised when a resume cannot be loaded or parsed."""


class ResumeParser:
    """Extracts plain text from supported local resume formats."""

    SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}

    def parse(self, path: Path) -> str:
        resume_path = path.expanduser().resolve()
        if not resume_path.exists():
            raise ResumeParseError(f"Resume file not found: {resume_path}")

        suffix = resume_path.suffix.lower()
        if suffix == ".txt":
            return self._parse_txt(resume_path)
        if suffix == ".pdf":
            return self._parse_pdf(resume_path)
        if suffix == ".docx":
            return self._parse_docx(resume_path)

        supported = ", ".join(sorted(self.SUPPORTED_SUFFIXES))
        raise ResumeParseError(
            f"Unsupported resume format '{suffix}'. Supported formats: {supported}"
        )

    @staticmethod
    def _parse_txt(path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ResumeParser._clean_text(text)

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ResumeParseError("pypdf is required to parse PDF resumes") from exc

        try:
            reader = PdfReader(str(path))
            parts = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise ResumeParseError(f"Failed to parse PDF resume: {exc}") from exc

        text = ResumeParser._clean_text("\n".join(parts))
        if not text:
            raise ResumeParseError("PDF resume did not contain extractable text")
        return text

    @staticmethod
    def _parse_docx(path: Path) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise ResumeParseError("python-docx is required to parse DOCX resumes") from exc

        try:
            document = Document(str(path))
            parts = [paragraph.text for paragraph in document.paragraphs]
        except Exception as exc:
            raise ResumeParseError(f"Failed to parse DOCX resume: {exc}") from exc

        text = ResumeParser._clean_text("\n".join(parts))
        if not text:
            raise ResumeParseError("DOCX resume did not contain extractable text")
        return text

    @staticmethod
    def _clean_text(text: str) -> str:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()
