"""Retry decorators using tenacity for resilient automation."""

from __future__ import annotations

import logging

from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    wait_fixed,
)

from job_agent.utils.exceptions import RateLimitError

logger = logging.getLogger("job_agent.utils.retry")


def retry_on_network_error(func):
    """Retry on network errors: 3 attempts, exponential backoff 2-30s with jitter."""
    return retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30, jitter=2),
        before=before_log(logger, logging.WARNING),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )(func)


def retry_on_stale_element(func):
    """Retry on stale DOM elements: 2 attempts, 1s fixed wait."""
    return retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True,
    )(func)


def retry_on_rate_limit(func):
    """Retry on rate limit (429) responses: 5 attempts, exponential 30-300s."""
    return retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=30, max=300, jitter=10),
        before=before_log(logger, logging.WARNING),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )(func)
