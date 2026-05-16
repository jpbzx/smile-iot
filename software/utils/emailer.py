import os
import smtplib
from email.message import EmailMessage


def send_password_reset_email(to_email: str, token: str, reset_url_base: str | None = None):
    """Send a password reset email containing a link with the token.

    Environment variables used (recommended to set in .env or environment):
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, RESET_URL_BASE

    Returns (True, None) on success or (False, error_message) on failure.
    """
    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    reset_base = reset_url_base or os.environ.get("RESET_URL_BASE", "http://localhost:8501/reset_password")
    reset_link = f"{reset_base}?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "SMILE-IoT: Password Reset Request"
    msg["From"] = smtp_user or "no-reply@smile-iot.local"
    msg["To"] = to_email
    msg.set_content(
        f"Hello,\n\nTo reset your SMILE-IoT password, click the link below:\n\n{reset_link}\n\nThis link expires in one hour.\n\nIf you didn't request this, please ignore this message.\n"
    )

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        try:
            server.starttls()
        except Exception:
            # StartTLS may fail if server doesn't support it; continue for local dev
            pass

        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)

        server.send_message(msg)
        server.quit()
        return True, None
    except Exception as e:
        return False, str(e)
