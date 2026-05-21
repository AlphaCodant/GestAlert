"""Envoi SMTP — pattern GESTREB."""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "mail.privateemail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("PWD", "")


def send_email(to: str, subject: str, body: str) -> None:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL][skipped, SMTP non configuré] To={to} Subject={subject}")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to, msg.as_string())
    except Exception as exc:
        print(f"[EMAIL] Erreur vers {to} : {exc}")
