"""
Email delivery via Resend HTTP API (works on Railway - no SMTP ports needed).

Required environment variables (same ones used in vivasuiza):
  RESEND_API_KEY      Resend API key
  RESEND_FROM_EMAIL   Verified sender address
"""
import os
import requests as _requests

_RESEND_URL = "https://api.resend.com/emails"


def is_email_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("RESEND_FROM_EMAIL"))


def send_api_key_email(to_email: str, api_key: str, app_name: str = "ETF Data API") -> None:
    """Send the newly created API key via Resend.

    Raises RuntimeError if credentials are missing.
    Raises requests.HTTPError on API failure.
    """
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr  = os.getenv("RESEND_FROM_EMAIL", "")

    if not resend_key or not from_addr:
        raise RuntimeError(
            "Email delivery is not configured. "
            "Set RESEND_API_KEY and RESEND_FROM_EMAIL on the backend service."
        )

    body_text = (
        f"Your API key for {app_name}:\n\n"
        f"  {api_key}\n\n"
        "Keep this key safe - it grants access to the API and will not be shown again.\n"
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
    Keep this key safe - it grants access to the API and will not be shown again.<br>
    Do not share it publicly.<br><br>
    Rate limit: 60 requests / minute.
  </p>
</body>
</html>"""

    resp = _requests.post(
        _RESEND_URL,
        headers={
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_addr,
            "to": [to_email],
            "subject": f"Your {app_name} API Key",
            "text": body_text,
            "html": body_html,
        },
        timeout=10,
    )
    resp.raise_for_status()
