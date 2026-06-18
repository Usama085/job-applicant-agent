"""Global constants and enums."""

from enum import Enum


class ApplicationStatus(str, Enum):
    APPLIED = "Applied"
    FAILED = "Failed"
    MANUAL_INTERVENTION = "Manual Intervention Required"
    SKIPPED = "Skipped"
    DUPLICATE = "Duplicate"


class RunStatus(str, Enum):
    RUNNING = "Running"
    COMPLETED = "Completed"
    CRASHED = "Crashed"


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"


# Circuit breaker: stop platform after this many consecutive failures
MAX_CONSECUTIVE_FAILURES = 3

# Maximum steps in a multi-step apply form (prevent infinite loops)
MAX_FORM_STEPS = 10

# Random skip rate for anti-detection (5-10% of jobs randomly skipped)
RANDOM_SKIP_RATE = 0.07
