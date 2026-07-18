"""Password-reset email delivery. With SMTP unconfigured (empty SMTP_HOST)
sending is disabled and the caller falls back to logging the token —
fine for LAN development, replace with real SMTP for anything else."""

import smtplib
from email.message import EmailMessage

from backend import config


def smtp_configured() -> bool:
    return bool(config.SMTP_HOST)


def send_password_reset_email(to_email: str, token: str) -> tuple[bool, str | None]:
    if not smtp_configured():
        return False, "smtp_disabled"

    reset_link = f"{config.RESET_URL_BASE}?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "SMILE-IoT: Password Reset Request"
    msg["From"] = config.SMTP_USER or "no-reply@smile-iot.local"
    msg["To"] = to_email
    msg.set_content(
        "Hello,\n\n"
        f"To reset your SMILE-IoT password, open:\n\n{reset_link}\n\n"
        "The link expires in one hour. If you didn't request this, ignore this message.\n"
    )

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            try:
                server.starttls()
            except smtplib.SMTPNotSupportedError:
                pass  # local dev relay without TLS
            if config.SMTP_USER and config.SMTP_PASSWORD:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True, None
    except Exception as exc:
        return False, str(exc)
