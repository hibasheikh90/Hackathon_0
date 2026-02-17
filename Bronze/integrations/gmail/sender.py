"""
Gold Tier — Gmail Sender
==========================
Upgraded from Silver gmail-send skill.
Now integrates with the event bus and error logger.

Usage:
    from integrations.gmail.sender import GmailSender

    sender = GmailSender()
    sender.send(to="ceo@company.com", subject="Weekly Report", body="See attached.")
"""

from __future__ import annotations

import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class GmailSender:
    """Send emails via Gmail SMTP with event bus integration."""

    def __init__(self) -> None:
        config.load()
        self.address = config.env("EMAIL_ADDRESS", "")
        self.password = config.env("EMAIL_PASSWORD", "")

    def is_configured(self) -> bool:
        """Check if Gmail credentials are set."""
        return bool(self.address and self.password)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        html: bool = False,
    ) -> bool:
        """Send an email. Returns True on success.

        Emits events: email.sent (success) or email.send_failed (failure).
        """
        if not self.is_configured():
            error_logger.log_error(
                "gmail.sender", "EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env"
            )
            return False

        # Build message
        msg = MIMEMultipart("alternative")
        msg["From"] = self.address
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        # Build recipient list
        recipients = [to]
        if cc:
            recipients += [addr.strip() for addr in cc.split(",") if addr.strip()]

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.address, self.password)
                server.sendmail(self.address, recipients, msg.as_string())

            bus.emit("email.sent", {
                "to": to,
                "subject": subject,
                "timestamp": datetime.now().isoformat(),
            })
            error_logger.log_audit("gmail.send", "success", {
                "to": to, "subject": subject,
            })
            return True

        except smtplib.SMTPAuthenticationError as e:
            error_logger.log_error("gmail.sender", e, {"to": to, "subject": subject})
            bus.emit("email.send_failed", {
                "to": to, "error": "Authentication failed",
            })
            return False
        except Exception as e:
            error_logger.log_error("gmail.sender", e, {"to": to, "subject": subject})
            bus.emit("email.send_failed", {
                "to": to, "error": str(e),
            })
            return False

    def send_alert(self, subject: str, body: str) -> bool:
        """Send an alert email to the configured CEO alert address."""
        alert_email = config.env("CEO_ALERT_EMAIL") or config.get("error_logging.alert_email")
        if not alert_email:
            error_logger.log_error("gmail.sender", "No CEO_ALERT_EMAIL configured")
            return False
        return self.send(to=alert_email, subject=f"[AI Employee Alert] {subject}", body=body)
