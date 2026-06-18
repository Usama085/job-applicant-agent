"""Gmail SMTP email client for sending notifications."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("job_agent.notifications.email_client")


class EmailClient:
    """Sends emails via Gmail SMTP with App Password authentication."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        address: str,
        app_password: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.address = address
        self.app_password = app_password

    def send(self, to: str, subject: str, html_body: str) -> bool:
        """Send an HTML email.

        Returns True on success, False on failure.
        """
        if not self.address or not self.app_password:
            logger.warning("Email not configured (missing address or app password)")
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = self.address
        msg["To"] = to
        msg["Subject"] = subject

        # Plain text fallback
        plain_text = html_body.replace("<br>", "\n").replace("</tr>", "\n")
        # Strip remaining HTML tags for plain text
        import re
        plain_text = re.sub(r"<[^>]+>", "", plain_text)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.address, self.app_password)
                server.send_message(msg)

            logger.info("Email sent: '%s' to %s", subject, to)
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Email authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD"
            )
            return False
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False
