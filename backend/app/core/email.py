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
    has_active_key: bool,
    api_key: str = None,
    app_name: str = "GoETF.ch API",
) -> None:
    """Send a confirmation email, including a new inactive API key when needed."""
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr  = os.getenv("RESEND_FROM_EMAIL", "")

    if not resend_key or not from_addr:
        raise RuntimeError(
            "Email delivery is not configured. "
            "Set RESEND_API_KEY and RESEND_FROM_EMAIL on the backend service."
        )

    if has_active_key:
        subject = f"{app_name} — Confirm Your Sign-In"
        key_text = "Your existing API key will remain unchanged.\n\n"
        key_html = """
  <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;
              padding:.85rem 1rem;margin-bottom:1.25rem;color:#1e40af;font-size:.9rem">
    An active API key already exists for this email address. Confirming will
    sign in this browser without changing that key.
  </div>"""
        key_markup = ""
        btn_label = "Confirm and Sign In"
    else:
        if not api_key:
            raise ValueError("A new API key is required for an unverified email address.")
        subject = f"{app_name} — Confirm Your API Key"
        key_text = (
            f"Your new API key is:\n\n  {api_key}\n\n"
            "It will remain inactive until you click the confirmation button.\n\n"
        )
        key_html = """
  <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;
              padding:.85rem 1rem;margin-bottom:1.25rem;color:#9a3412;font-size:.9rem">
    This new key will remain inactive until you confirm your email address.
  </div>"""
        key_markup = f"""
  <p>Your new API key:</p>
  <pre style="background:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;padding:1rem 1.25rem;
              font-size:1rem;letter-spacing:.04em;word-break:break-all">{api_key}</pre>"""
        btn_label = "Confirm Email and Activate Key"

    body_text = (
        f"You requested access to {app_name}.\n\n"
        f"{key_text}"
        f"Confirm by visiting:\n{confirm_url}\n\n"
        "This link expires in 30 minutes.\n"
        "If you did not request this, ignore this email. A new key will not be activated.\n"
    )

    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:520px;margin:2rem auto;padding:0 1rem">
  <h2 style="margin-bottom:.25rem">{app_name}</h2>
  <p style="color:#555;margin-top:.25rem">You requested access to {app_name}.</p>
  {key_html}
  {key_markup}
  <p>Click the button below to confirm. The link expires in <strong>30 minutes</strong>.</p>
  <a href="{confirm_url}"
     style="display:inline-block;background:#16a34a;color:#fff;text-decoration:none;
            padding:.75rem 1.5rem;border-radius:8px;font-weight:600;font-size:1rem;
            margin:.5rem 0 1rem">{btn_label}</a>
  <p style="color:#888;font-size:.8rem">
    If you did not request this, ignore this email. A new key will not be activated.
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
