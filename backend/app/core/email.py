"""
Email utilities — SMTP-based delivery.

Required environment variables:
  SMTP_HOST       e.g. smtp.gmail.com  or  smtp.sendgrid.net
  SMTP_PORT       default 587 (STARTTLS)
  SMTP_USER       login username / sender address
  SMTP_PASSWORD   login password / API key
  SMTP_FROM       optional display "From" address (falls back to SMTP_USER)
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_config() -> tuple[str, int, str, str, str]:
    host     = os.getenv("SMTP_HOST", "")
    port     = int(os.getenv("SMTP_PORT", "587"))
    user     = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_    = os.getenv("SMTP_FROM", user)
    return host, port, user, password, from_


def is_email_configured() -> bool:
    host, _, user, password, _ = _smtp_config()
    return bool(host and user and password)


def send_api_key_email(to_email: str, api_key: str, app_name: str = "ETF Data API") -> None:
    """Send the newly created API key to the user's email address.

    Raises RuntimeError if SMTP is not configured.
    Raises smtplib.SMTPException (or subclass) on delivery failure.
    """
    host, port, user, password, from_ = _smtp_config()
    if not host or not user or not password:
        raise RuntimeError(
            "Email delivery is not configured on this server. "
            "Set the SMTP_HOST, SMTP_USER and SMTP_PASSWORD environment variables."
        )

    subject = f"Your {app_name} API Key"

    body_text = (
        f"Your API key for {app_name}:\n\n"
        f"  {api_key}\n\n"
        "Keep this key safe — it grants access to the API and will not be shown again.\n"
        "Do not share it publicly.\n\n"
        "Rate limit: 60 requests / minute.\n"
    )

    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:520px;margin:2rem auto;padding:0 1rem">
  <h2 style="margin-bottom:.5rem">{app_name}</h2>
  <p>Here is your API key:</p>
  <pre style="background:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;padding:1rem 1.25rem;
              font-size:1rem;letter-spacing:.04em;word-break:break-all">{api_key}</pre>
  <p style="color:#555;font-size:.9rem">
    Keep this key safe — it grants access to the API and will not be shown again.<br>
    Do not share it publicly.<br><br>
    Rate limit: 60 requests / minute.
  </p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.sendmail(from_, to_email, msg.as_string())
