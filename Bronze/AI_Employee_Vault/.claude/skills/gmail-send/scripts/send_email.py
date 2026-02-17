"""
Skill: gmail-send
Sends real emails through Gmail SMTP using App Passwords.
"""

import argparse
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# Load .env from Bronze directory (walk up from this script to find it)
_script_dir = Path(__file__).resolve().parent
for _parent in _script_dir.parents:
    _env_path = _parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path)
        break

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def get_credentials() -> tuple[str, str]:
    address = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()

    if not address:
        print("[ERROR] EMAIL_ADDRESS environment variable is not set.")
        sys.exit(1)
    if not password:
        print("[ERROR] EMAIL_PASSWORD environment variable is not set.")
        print("        Use a Gmail App Password: https://myaccount.google.com/apppasswords")
        sys.exit(1)

    return address, password


def build_message(
    sender: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    html: bool = False,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = cc

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    return msg


def send(msg: MIMEMultipart, sender: str, password: str, recipients: list[str]) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an email via Gmail SMTP.")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--body", required=True, help="Email body text")
    parser.add_argument("--cc", default=None, help="CC recipients (comma-separated)")
    parser.add_argument("--html", action="store_true", help="Send body as HTML")
    args = parser.parse_args()

    sender, password = get_credentials()

    # Build recipient list
    recipients = [args.to]
    if args.cc:
        recipients += [addr.strip() for addr in args.cc.split(",") if addr.strip()]

    msg = build_message(
        sender=sender,
        to=args.to,
        subject=args.subject,
        body=args.body,
        cc=args.cc,
        html=args.html,
    )

    try:
        send(msg, sender, password, recipients)
    except smtplib.SMTPAuthenticationError:
        print("[ERROR] Authentication failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD.")
        print("        Make sure you are using a Gmail App Password, not your account password.")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[OK] Email sent to {args.to}")
    print(f"  Subject: {args.subject}")
    print(f"  Timestamp: {timestamp}")


if __name__ == "__main__":
    main()
