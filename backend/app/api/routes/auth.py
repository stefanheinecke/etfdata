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

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.db.database import get_db
from app.core.auth import (
    create_api_key,
    generate_api_key,
    get_google_account_for_session,
    hash_api_key,
    verify_api_key,
)
from app.core.email import send_confirmation_email, send_api_key_email, is_email_configured
from app.schemas import APIKey, GoogleAccount, PendingKeyRequest, ContactMessage, Settings, WebSession

router = APIRouter(prefix="/auth", tags=["auth"])

_APP_NAME = "GoETF.ch API"
_GOOGLE_SESSION_COOKIE = "web_session"
_GOOGLE_SESSION_DAYS = 7


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
    try:
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
        base_url    = os.getenv("API_BASE_URL", "https://api.goetf.ch")
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
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


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


@router.get("/me")
def get_current_user(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
):
    """Return the name and email associated with the current API key."""
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    is_admin = bool(admin_email and api_key.email and api_key.email.strip().lower() == admin_email)
    return {"name": api_key.name, "email": api_key.email, "is_admin": is_admin}


# ── Contact Form ──────────────────────────────────────────────────────────────

class ContactFormRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


class ContactFormResponse(BaseModel):
    message: str
    success: bool


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)


def _verified_google_claims(credential: str) -> dict:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            GoogleRequest(),
            client_id,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google sign-in credential.")
    except google_auth_exceptions.GoogleAuthError:
        raise HTTPException(status_code=503, detail="Google sign-in verification is unavailable.")

    email = claims.get("email")
    subject = claims.get("sub")
    if (
        not isinstance(email, str)
        or not email
        or not isinstance(subject, str)
        or not subject
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(status_code=401, detail="A verified Google email address is required.")

    name = claims.get("name")
    if not isinstance(name, str) or not name.strip():
        name = email.split("@")[0]

    return {
        "google_sub": subject,
        "email": email.strip().lower()[:255],
        "name": name.strip()[:255],
    }


def _session_cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes"}


def _session_cookie_samesite() -> str:
    return "none" if _session_cookie_secure() else "lax"


def _find_usable_api_key(db: Session, email: str):
    now = datetime.utcnow()
    return db.query(APIKey).filter(
        APIKey.email == email,
        APIKey.is_active.is_(True),
        or_(APIKey.expires_at.is_(None), APIKey.expires_at > now),
    ).order_by(APIKey.created_at.desc()).first()


@router.post("/google/session")
def google_session(
    payload: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Verify a Google ID token and start a server-side web session."""
    claims = _verified_google_claims(payload.credential)
    account = db.query(GoogleAccount).filter(
        GoogleAccount.google_sub == claims["google_sub"]
    ).first()
    if account:
        account.email = claims["email"]
        account.name = claims["name"]
        account.updated_at = datetime.utcnow()
    else:
        account = GoogleAccount(**claims)
        db.add(account)
        db.flush()

    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=_GOOGLE_SESSION_DAYS)
    db.add(WebSession(
        google_account_id=account.id,
        token_hash=hash_api_key(session_token),
        expires_at=expires_at,
    ))
    db.commit()

    api_key_emailed = False
    api_key_email_error = None
    if not _find_usable_api_key(db, account.email):
        raw_key = generate_api_key()
        db.add(APIKey(
            key=hash_api_key(raw_key),
            name=account.email.split("@")[0][:100],
            email=account.email,
            rate_limit_per_minute=60,
        ))
        try:
            send_api_key_email(to_email=account.email, api_key=raw_key)
            db.commit()
            api_key_emailed = True
        except (RuntimeError, _requests.RequestException):
            db.rollback()
            import logging
            logging.getLogger(__name__).exception(
                "Could not email an API key to the Google-authenticated user."
            )
            api_key_email_error = (
                "You are signed in, but we could not email your API key. "
                "Please try Google sign-in again or request a key by email."
            )

    response.set_cookie(
        key=_GOOGLE_SESSION_COOKIE,
        value=session_token,
        max_age=_GOOGLE_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path="/",
    )
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    return {
        "name": account.name,
        "email": account.email,
        "is_admin": bool(admin_email and account.email == admin_email),
        "has_api_key": _find_usable_api_key(db, account.email) is not None,
        "api_key_emailed": api_key_emailed,
        "api_key_email_error": api_key_email_error,
    }


@router.get("/session")
def get_web_session(
    web_session: str = Cookie(None),
    db: Session = Depends(get_db),
):
    account = get_google_account_for_session(web_session, db)
    if not account:
        raise HTTPException(status_code=401, detail="No active Google session.")

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    return {
        "name": account.name,
        "email": account.email,
        "is_admin": bool(admin_email and account.email == admin_email),
        "has_api_key": _find_usable_api_key(db, account.email) is not None,
    }


@router.post("/logout")
def logout_google_session(
    response: Response,
    web_session: str = Cookie(None),
    db: Session = Depends(get_db),
):
    if web_session:
        session = db.query(WebSession).filter(
            WebSession.token_hash == hash_api_key(web_session),
            WebSession.revoked_at.is_(None),
        ).first()
        if session:
            session.revoked_at = datetime.utcnow()
            db.commit()

    response.delete_cookie(
        key=_GOOGLE_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
    )
    return {"message": "Signed out."}


@router.post("/contact", response_model=ContactFormResponse)
def submit_contact_form(contact: ContactFormRequest, db: Session = Depends(get_db)):
    """
    Submit a contact form message. Stores it in the database and attempts to send
    an email to the configured contact email address.
    """
    try:
        # Validate input
        if not contact.name or len(contact.name.strip()) < 2:
            raise HTTPException(status_code=422, detail="Name is required (at least 2 characters)")
        
        if not contact.email or "@" not in contact.email:
            raise HTTPException(status_code=422, detail="Valid email address is required")
        
        if not contact.message or len(contact.message.strip()) < 10:
            raise HTTPException(status_code=422, detail="Message is required (at least 10 characters)")
        
        # Store the contact message
        msg = ContactMessage(
            name=contact.name.strip()[:255],
            email=str(contact.email).strip().lower()[:255],
            message=contact.message.strip()
        )
        db.add(msg)
        db.commit()
        
        # Try to send email to the contact email address (from settings)
        if is_email_configured():
            try:
                import logging
                logger = logging.getLogger(__name__)
                
                contact_email_setting = db.query(Settings).filter(Settings.key == "contact_email").first()
                contact_email = contact_email_setting.value if contact_email_setting else "stefan.heinecke1@gmail.com"
                
                logger.info(f"📧 Sending contact form email to: {contact_email}")
                
                # Send email using Resend
                resend_key = os.getenv("RESEND_API_KEY", "")
                from_addr  = os.getenv("RESEND_FROM_EMAIL", "")
                
                # Log without exposing full API key
                key_preview = (resend_key[:20] + "...") if resend_key else "(not set)"
                logger.info(f"📧 Email config - From: {from_addr}, API key: {key_preview}")
                
                if resend_key and from_addr:
                    response = _requests.post(
                        "https://api.resend.com/emails",
                        headers={"Authorization": f"Bearer {resend_key}"},
                        json={
                            "from": from_addr,
                            "to": contact_email,
                            "subject": f"New contact form submission from {contact.name}",
                            "html": f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:520px;margin:2rem auto;padding:0 1rem">
  <h2>New Contact Form Submission</h2>
  <p><strong>From:</strong> {contact.name} ({contact.email})</p>
  <hr style="border:none;border-top:1px solid #e4e4e7;margin:1.5rem 0">
  <p><strong>Message:</strong></p>
  <p style="white-space:pre-wrap">{contact.message}</p>
  <hr style="border:none;border-top:1px solid #e4e4e7;margin:1.5rem 0">
  <p style="font-size:.85rem;color:#888">
    Reply to: <a href="mailto:{contact.email}">{contact.email}</a>
  </p>
</body>
</html>"""
                        }
                    )
                    logger.info(f"📧 Resend response: {response.status_code}")
                    if response.status_code != 200:
                        logger.error(f"📧 Resend error response: {response.text}")
                    response.raise_for_status()
                    logger.info(f"✅ Email sent successfully to {contact_email}")
                else:
                    logger.warning("📧 Resend credentials not available")
            except Exception as e:
                # Log the error but don't fail the request — the message was stored
                import logging
                logging.getLogger(__name__).error(f"❌ Failed to send contact email: {e}", exc_info=True)
        
        return {
            "message": "Thank you! Your message has been sent. We'll get back to you soon.",
            "success": True
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
