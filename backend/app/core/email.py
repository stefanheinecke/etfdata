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


def send_api_key_email(to_email: str, api_key: str, app_name: str = "GoETF.ch API") -> None:
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


def send_confirmation_email(
    to_email: str,
    confirm_url: str,
    is_replacement: bool,
    app_name: str = "GoETF.ch API",
) -> None:
    """Send a confirmation email with a button to claim (or replace) an API key."""
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr  = os.getenv("RESEND_FROM_EMAIL", "")

    if not resend_key or not from_addr:
        raise RuntimeError(
            "Email delivery is not configured. "
            "Set RESEND_API_KEY and RESEND_FROM_EMAIL on the backend service."
        )

    if is_replacement:
        subject      = f"{app_name} — Confirm API Key Reset"
        warning_text = (
            "⚠ WARNING: An API key already exists for this email address.\n"
            "Clicking the button below will REPLACE your existing key.\n"
            "Your old key will stop working immediately.\n\n"
        )
        warning_html = """
  <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;
              padding:.85rem 1rem;margin-bottom:1.25rem;color:#9a3412;font-size:.9rem">
    <strong>⚠ Warning:</strong> An API key already exists for this email address.<br>
    Clicking the button below will <strong>replace your existing key</strong>.
    Your old key will stop working immediately.
  </div>"""
        btn_label = "Yes, Replace My API Key"
    else:
        subject      = f"{app_name} — Confirm Your API Key Request"
        warning_text = ""
        warning_html = ""
        btn_label    = "Get My API Key"

    body_text = (
        f"You requested an API key for {app_name}.\n\n"
        f"{warning_text}"
        f"Confirm by visiting:\n{confirm_url}\n\n"
        "This link expires in 30 minutes.\n"
        "If you did not request this, ignore this email.\n"
    )

    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:520px;margin:2rem auto;padding:0 1rem">
  <h2 style="margin-bottom:.25rem">{app_name}</h2>
  <p style="color:#555;margin-top:.25rem">You requested an API key.</p>
  {warning_html}
  <p>Click the button below to confirm. The link expires in <strong>30 minutes</strong>.</p>
  <a href="{confirm_url}"
     style="display:inline-block;background:#16a34a;color:#fff;text-decoration:none;
            padding:.75rem 1.5rem;border-radius:8px;font-weight:600;font-size:1rem;
            margin:.5rem 0 1rem">{btn_label}</a>
  <p style="color:#888;font-size:.8rem">
    If you did not request this, ignore this email — no key will be created.
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
            "subject": subject,
            "text": body_text,
            "html": body_html,
        },
        timeout=10,
    )
    resp.raise_for_status()
