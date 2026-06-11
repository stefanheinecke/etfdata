"""
Public auth routes — no admin secret required.

Two-step API key flow:
  1. POST /auth/request-key   — validate email, store token, send confirmation email
  2. GET  /auth/confirm-key   — validate token, create/replace key, send key email, show HTML page
"""
import os
import secrets
import requests as _requests
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import create_api_key, generate_api_key, hash_api_key
from app.core.email import send_confirmation_email, send_api_key_email
from app.schemas import APIKey, PendingKeyRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_APP_NAME = "ETF Data API"


# ── HTML templates ────────────────────────────────────────────────────────────

def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {_APP_NAME}</title>
<style>
  body{{font-family:sans-serif;background:#f9fafb;color:#111;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0;padding:1rem}}
  .card{{background:#fff;border-radius:12px;padding:2rem 2.5rem;max-width:460px;
         width:100%;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  h1{{font-size:1.4rem;margin:0 0 .5rem}}
  p{{color:#555;font-size:.95rem;line-height:1.6;margin:.5rem 0}}
  .icon{{font-size:2.5rem;margin-bottom:.75rem}}
</style>
</head>
<body><div class="card">{body}</div></body>
</html>"""


def _success_page(email: str) -> str:
    return _page("Key Sent", f"""
  <div class="icon">✉️</div>
  <h1>API Key Sent!</h1>
  <p>Your API key has been sent to <strong>{email}</strong>.</p>
  <p>Check your inbox (and spam folder) — it may take a minute to arrive.</p>
  <p style="font-size:.85rem;color:#888;margin-top:1.25rem">
    Keep your key safe. Do not share it publicly.
  </p>""")


def _error_page(message: str) -> str:
    return _page("Error", f"""
  <div class="icon">⚠️</div>
  <h1>Something went wrong</h1>
  <p>{message}</p>""")


# ── Step 1: request ───────────────────────────────────────────────────────────

@router.post("/request-key")
def request_key(email: str, db: Session = Depends(get_db)):
    """
    Validate the email, store a one-time confirmation token, and send a
    confirmation email. Returns immediately without creating an API key.
    """
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")

    email = email.strip().lower()[:255]

    # Check whether a key already exists for this email
    is_replacement = db.query(APIKey).filter(APIKey.email == email).first() is not None

    # Remove any previous pending request for this email (re-request scenario)
    db.query(PendingKeyRequest).filter(PendingKeyRequest.email == email).delete()

    # Store a fresh token valid for 30 minutes
    token   = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=30)
    db.add(PendingKeyRequest(token=token, email=email,
                             is_replacement=is_replacement, expires_at=expires))
    db.commit()

    # Build the confirmation URL (backend endpoint — returns an HTML page)
    base_url    = os.getenv("API_BASE_URL", "https://etfdata-production.up.railway.app")
    confirm_url = f"{base_url}/auth/confirm-key?token={token}"

    try:
        send_confirmation_email(to_email=email, confirm_url=confirm_url,
                                is_replacement=is_replacement)
    except (RuntimeError, _requests.HTTPError) as exc:
        db.query(PendingKeyRequest).filter(PendingKeyRequest.token == token).delete()
        db.commit()
        detail = str(exc) if isinstance(exc, RuntimeError) else \
                 f"Email delivery failed: {exc.response.text if exc.response else exc}"
        raise HTTPException(status_code=503, detail=detail)

    return {
        "message": "Confirmation email sent. Click the link in the email to receive your API key.",
        "email": email,
    }


# ── Step 2: confirm ───────────────────────────────────────────────────────────

@router.get("/confirm-key", response_class=HTMLResponse)
def confirm_key(token: str, db: Session = Depends(get_db)):
    """
    Validate the one-time token, create or replace the API key, send the key
    by email, and return an HTML page with the result.
    """
    pending = db.query(PendingKeyRequest).filter(
        PendingKeyRequest.token == token
    ).first()

    if not pending:
        return HTMLResponse(_error_page(
            "This confirmation link is invalid or has already been used."
        ), status_code=400)

    if pending.expires_at < datetime.utcnow():
        db.delete(pending)
        db.commit()
        return HTMLResponse(_error_page(
            "This confirmation link has expired (links are valid for 30 minutes). "
            "Please request a new API key."
        ), status_code=400)

    email          = pending.email
    is_replacement = pending.is_replacement

    # Consume the token immediately so it cannot be reused
    db.delete(pending)
    db.commit()

    # Create or replace the key
    if is_replacement:
        existing = db.query(APIKey).filter(APIKey.email == email).first()
        if existing:
            raw_key      = generate_api_key()
            existing.key = hash_api_key(raw_key)
            db.commit()
            db_key = existing
        else:
            # Key was deleted between request and confirm — create fresh
            raw_key, db_key = create_api_key(db, name=email.split("@")[0][:100], email=email)
    else:
        raw_key, db_key = create_api_key(db, name=email.split("@")[0][:100], email=email)

    # Deliver the key
    try:
        send_api_key_email(to_email=email, api_key=raw_key)
    except Exception as exc:
        return HTMLResponse(_error_page(
            f"Your key was created but could not be delivered: {exc}. "
            "Please contact the administrator."
        ), status_code=500)

    return HTMLResponse(_success_page(email))
