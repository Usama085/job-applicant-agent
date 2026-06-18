"""Custom exception hierarchy for the job agent."""


class JobAgentError(Exception):
    """Base exception for all agent errors."""


class BrowserSessionError(JobAgentError):
    """Browser failed to launch, context is corrupt, or page crashed."""


class LoginExpiredError(BrowserSessionError):
    """Saved cookies/session no longer valid. Manual re-login needed."""

    def __init__(self, platform: str):
        self.platform = platform
        super().__init__(f"[{platform}] Session expired, manual re-login required")


class PlatformError(JobAgentError):
    """Error interacting with a specific job platform."""

    def __init__(self, platform: str, message: str):
        self.platform = platform
        super().__init__(f"[{platform}] {message}")


class CaptchaDetectedError(PlatformError):
    """CAPTCHA, OTP, or security challenge detected."""

    def __init__(self, platform: str, captcha_type: str, job_url: str):
        self.captcha_type = captcha_type
        self.job_url = job_url
        super().__init__(platform, f"CAPTCHA detected ({captcha_type}) at {job_url}")


class FormFillingError(PlatformError):
    """Could not fill a required form field."""

    def __init__(self, platform: str, field_name: str, reason: str):
        self.field_name = field_name
        super().__init__(platform, f"Form fill failed for '{field_name}': {reason}")


class ApplicationLimitReachedError(PlatformError):
    """Daily application limit reached for this platform."""

    def __init__(self, platform: str):
        super().__init__(platform, "Daily application limit reached")


class RateLimitError(PlatformError):
    """Platform returned a rate-limit response (429 or equivalent)."""

    def __init__(self, platform: str):
        super().__init__(platform, "Rate limit hit (429)")
