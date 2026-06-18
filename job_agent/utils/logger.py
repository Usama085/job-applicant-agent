"""Logging configuration with rotating file handler and console output."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_file: Path,
    log_level: str = "INFO",
    max_bytes: int = 5_242_880,
    backup_count: int = 5,
) -> None:
    """Configure the root 'job_agent' logger with file and console handlers."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("job_agent")
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid adding duplicate handlers on re-initialization
    if root.handlers:
        return

    # File handler: rotating, structured format
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler: concise format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root.addHandler(file_handler)
    root.addHandler(console_handler)
