"""Resume file upload handler for job applications."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("job_agent.forms.resume_uploader")


class ResumeUploader:
    """Detects file upload inputs and attaches the resume PDF."""

    def __init__(self, resume_path: Path):
        self.resume_path = resume_path
        if not self.resume_path.exists():
            logger.warning("Resume file not found: %s", self.resume_path)

    async def upload_if_needed(
        self, page: Page, container_selector: str = "body"
    ) -> bool:
        """Detect file input in container and upload resume if found.

        Returns True if a resume was uploaded, False if no upload was needed.
        """
        if not self.resume_path.exists():
            logger.error("Resume file missing: %s", self.resume_path)
            return False

        # Find file input elements
        file_inputs = page.locator(f"{container_selector} input[type='file']")
        count = await file_inputs.count()

        if count == 0:
            return False

        # Upload to the first file input found
        file_input = file_inputs.first
        try:
            await file_input.set_input_files(str(self.resume_path))
            logger.info("Resume uploaded: %s", self.resume_path.name)
            return True
        except Exception as e:
            logger.warning("Failed to upload resume: %s", e)
            return False

    async def upload_to_selector(self, page: Page, selector: str) -> bool:
        """Upload resume to a specific file input selector.

        Returns True if successful.
        """
        if not self.resume_path.exists():
            logger.error("Resume file missing: %s", self.resume_path)
            return False

        try:
            element = page.locator(selector)
            await element.set_input_files(str(self.resume_path))
            logger.info("Resume uploaded to %s", selector)
            return True
        except Exception as e:
            logger.warning("Failed to upload resume to %s: %s", selector, e)
            return False
