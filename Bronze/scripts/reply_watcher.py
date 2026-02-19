"""
Watches Gmail inbox for a reply from a specific sender.
When found, sends a notification email to the configured address.
"""

import imaplib
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    from dotenv import load_dotenv
    for _parent in [Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents):
        _env = _parent / ".env"
        if _env.is_file():
            load_dotenv(_env)
            break
except ImportError:
    pass

WATCH_FROM = os.environ.get("REPLY_WATCH_FROM", "hayashi.a@vivint.solar")
INTERVAL = int(os.environ.get("REPLY_WATCH_INTERVAL", "60"))


def get_credentials():
    addr = os.environ.get("EMAIL_ADDRESS", "").strip()
    pwd = os.environ.get("EMAIL_PASSWORD", "").strip()
    if not addr or not pwd:
        print("[ERROR] EMAIL_ADDRESS or EMAIL_PASSWORD not set.")
        sys.exit(1)
    return addr, pwd


def check_for_reply(addr, pwd):
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(addr, pwd)
    mail.select("INBOX")
    status, data = mail.search(None, "FROM", WATCH_FROM)
    ids = data[0].split()
    header = None
    if ids:
        _, msg_data = mail.fetch(ids[-1], "(BODY[HEADER.FIELDS (SUBJECT DATE FROM)])")
        header = msg_data[0][1].decode()
    mail.logout()
    return ids, header


def send_notification(addr, pwd, header):
    msg = MIMEMultipart()
    msg["From"] = addr
    msg["To"] = addr
    msg["Subject"] = f"[ALERT] Reply received from {WATCH_FROM}"
    body = (
        f"A reply has been received from {WATCH_FROM}:\n\n"
        f"{header}\n\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(addr, pwd)
        s.sendmail(addr, [addr], msg.as_string())


def main():
    addr, pwd = get_credentials()
    print(f"[INFO] Watching for reply from {WATCH_FROM} (interval: {INTERVAL}s)")
    print(f"[INFO] Notification will be sent to {addr}")

    while True:
        try:
            ids, header = check_for_reply(addr, pwd)
            if ids:
                print(f"[OK] Reply detected from {WATCH_FROM}!")
                send_notification(addr, pwd, header)
                print(f"[OK] Notification email sent to {addr}")
                break
            else:
                print(f"[INFO] {datetime.now().strftime('%H:%M:%S')} — No reply yet. Next check in {INTERVAL}s...")
                time.sleep(INTERVAL)
        except Exception as e:
            print(f"[ERROR] {e}. Retrying in {INTERVAL}s...")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
