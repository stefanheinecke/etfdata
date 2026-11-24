"""
Public auth routes — no admin secret required.

Two-step API key flow:
  1. POST /auth/request-key   — create an inactive key if needed and send a confirmation email
  2. GET  /auth/confirm-key   — activate the key and sign in the confirming browser
"""
import html
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import requests as _requests
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
    generate_api_key,
    get_email_session,
    hash_api_key,
    verify_api_key,
)
from app.core.email import (
    is_email_configured,
    send_api_key_email,
    send_confirmation_email,
)
from app.schemas import (
    APIKey,
    ContactMessage,
    EmailWebSession,
    GoogleAccount,
    PendingKeyRequest,
    Settings,
    WebSession,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_APP_NAME = "GoETF.ch API"
_GOOGLE_SESSION_COOKIE = "web_session"
_GOOGLE_SESSION_DAYS = 7
_PENDING_EMAIL_COOKIE = "pending_email_session"


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
    frontend_url = html.escape(
        os.getenv("FRONTEND_URL", "https://trueetf.com").strip().rstrip("/"),
        quote=True,
    )
    safe_email = html.escape(email)
    return _page("Email Confirmed", f"""
  <div class="icon">✅</div>
  <h1>Email Confirmed</h1>
  <p>The email address <strong>{safe_email}</strong> is confirmed.</p>
  <p>This browser is now signed in. Any new API key associated with this request is active.</p>
  <p><a href="{frontend_url}">Continue to TrueETF</a></p>
  <p style="font-size:.85rem;color:#888;margin-top:1.25rem">
    Existing active API keys are left unchanged.
  </p>""")


def _error_page(message: str) -> str:
    return _page("Error", f"""
  <div class="icon">⚠️</div>
  <h1>Something went wrong</h1>
  <p>{message}</p>""")


# ── Step 1: request ───────────────────────────────────────────────────────────

@router.post("/request-key")
def request_key(
    email: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Send a confirmation email and create an inactive key if the email has none.
    """
    try:
        if not email or "@" not in email:
            raise HTTPException(status_code=422, detail="A valid email address is required.")

        email = email.strip().lower()[:255]

        has_active_key = _find_usable_api_key(db, email) is not None
        db.query(PendingKeyRequest).filter(
            PendingKeyRequest.email == email
        ).delete()

        raw_key = None
        if not has_active_key:
            raw_key = generate_api_key()
            inactive_key = db.query(APIKey).filter(
                APIKey.email == email,
                APIKey.is_active.is_(False),
            ).order_by(APIKey.created_at.desc()).first()
            if inactive_key:
                inactive_key.key = hash_api_key(raw_key)
                inactive_key.name = email.split("@")[0][:100]
                inactive_key.created_at = datetime.utcnow()
                inactive_key.expires_at = None
            else:
                db.add(APIKey(
                    key=hash_api_key(raw_key),
                    name=email.split("@")[0][:100],
                    email=email,
                    rate_limit_per_minute=60,
                    is_active=False,
                ))

        token = secrets.token_urlsafe(32)
        browser_token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(minutes=30)
        db.add(PendingKeyRequest(
            token=token,
            email=email,
            browser_token_hash=hash_api_key(browser_token),
            is_replacement=has_active_key,
            expires_at=expires,
        ))
        base_url = os.getenv("API_BASE_URL", "https://api.goetf.ch")
        confirm_url = f"{base_url}/auth/confirm-key?token={token}"

        try:
            db.flush()
            send_confirmation_email(
                to_email=email,
                confirm_url=confirm_url,
                has_active_key=has_active_key,
                api_key=raw_key,
            )
            db.commit()
        except (RuntimeError, _requests.RequestException) as exc:
            db.rollback()
            detail = str(exc) if isinstance(exc, RuntimeError) else \
                     f"Email delivery failed: {exc.response.text if exc.response else exc}"
            raise HTTPException(status_code=503, detail=detail)

        _set_pending_email_cookie(response, browser_token)
        return {
            "message": "A confirmation email was sent. Confirm your email to activate access.",
            "email": email,
            "has_active_key": has_active_key,
        }
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


# ── Step 2: confirm ───────────────────────────────────────────────────────────

@router.get("/confirm-key", response_class=HTMLResponse)
def confirm_key(
    token: str,
    pending_email_session: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Validate the one-time token, activate a pending API key, and sign in this
    browser without replacing any existing active key.
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

    if pending.confirmed_at:
        return HTMLResponse(_error_page(
            "This confirmation link has already been used."
        ), status_code=400)

    email = pending.email
    active_key = _find_usable_api_key(db, email)
    raw_key = None
    if not active_key:
        if pending.is_replacement:
            db.delete(pending)
            db.commit()
            return HTMLResponse(_error_page(
                "The existing API key is no longer active. Please request a new key."
            ), status_code=409)

        inactive_key = db.query(APIKey).filter(
            APIKey.email == email,
            APIKey.is_active.is_(False),
        ).order_by(APIKey.created_at.desc()).first()
        if inactive_key:
            inactive_key.is_active = True
        else:
            # Support confirmation links issued before inactive keys were created at request time.
            raw_key = generate_api_key()
            db.add(APIKey(
                key=hash_api_key(raw_key),
                name=email.split("@")[0][:100],
                email=email,
                rate_limit_per_minute=60,
                is_active=True,
            ))

    session_token = secrets.token_urlsafe(32)
    db.add(EmailWebSession(
        email=email,
        token_hash=hash_api_key(session_token),
        expires_at=datetime.utcnow() + timedelta(days=_GOOGLE_SESSION_DAYS),
    ))
    same_browser = bool(
        pending_email_session
        and pending.browser_token_hash == hash_api_key(pending_email_session)
    )
    if same_browser:
        db.delete(pending)
    else:
        pending.confirmed_at = datetime.utcnow()
        pending.expires_at = pending.confirmed_at + timedelta(days=_GOOGLE_SESSION_DAYS)

    try:
        if raw_key:
            send_api_key_email(to_email=email, api_key=raw_key)
        db.commit()
    except (RuntimeError, _requests.RequestException) as exc:
        db.rollback()
        return HTMLResponse(_error_page(
            f"Your confirmation could not be completed: {exc}. Please try again."
        ), status_code=500)

    success_response = HTMLResponse(_success_page(email))
    _set_web_session_cookie(success_response, session_token)
    if same_browser:
        _delete_pending_email_cookie(success_response)
    return success_response


@router.get("/email-status")
def email_confirmation_status(
    response: Response,
    pending_email_session: Optional[str] = Cookie(None),
    web_session: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if pending_email_session:
        pending = db.query(PendingKeyRequest).filter(
            PendingKeyRequest.browser_token_hash == hash_api_key(pending_email_session)
        ).first()
        if pending:
            now = datetime.utcnow()
            if pending.expires_at < now:
                db.delete(pending)
                db.commit()
                _delete_pending_email_cookie(response)
            elif not pending.confirmed_at:
                return {"pending": True, "authenticated": False}
            else:
                api_key = _find_usable_api_key(db, pending.email)
                if not api_key:
                    db.delete(pending)
                    db.commit()
                    _delete_pending_email_cookie(response)
                else:
                    session_token = secrets.token_urlsafe(32)
                    db.add(EmailWebSession(
                        email=pending.email,
                        token_hash=hash_api_key(session_token),
                        expires_at=now + timedelta(days=_GOOGLE_SESSION_DAYS),
                    ))
                    email = pending.email
                    pending.browser_token_hash = None
                    db.delete(pending)
                    db.commit()

                    _set_web_session_cookie(response, session_token)
                    _delete_pending_email_cookie(response)
                    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
                    return {
                        "pending": False,
                        "authenticated": True,
                        "name": api_key.name,
                        "email": email,
                        "is_admin": bool(admin_email and email == admin_email),
                        "has_api_key": True,
                    }
        else:
            _delete_pending_email_cookie(response)

    email_session = get_email_session(web_session, db)
    if email_session:
        api_key = _find_usable_api_key(db, email_session.email)
        if api_key:
            _delete_pending_email_cookie(response)
            admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
            return {
                "pending": False,
                "authenticated": True,
                "name": api_key.name,
                "email": email_session.email,
                "is_admin": bool(admin_email and email_session.email == admin_email),
                "has_api_key": True,
            }

    return {"pending": False, "authenticated": False}


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


def _set_web_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_GOOGLE_SESSION_COOKIE,
        value=token,
        max_age=_GOOGLE_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path="/",
    )


def _set_pending_email_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_PENDING_EMAIL_COOKIE,
        value=token,
        max_age=_GOOGLE_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path="/",
    )


def _delete_pending_email_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_PENDING_EMAIL_COOKIE,
        path="/",
        httponly=True,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
    )


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

    _set_web_session_cookie(response, session_token)
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
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    email = api_key.email
    return {
        "name": api_key.name,
        "email": email,
        "is_admin": bool(admin_email and email and email.strip().lower() == admin_email),
        "has_api_key": _find_usable_api_key(db, email) is not None if email else False,
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
        email_session = db.query(EmailWebSession).filter(
            EmailWebSession.token_hash == hash_api_key(web_session),
            EmailWebSession.revoked_at.is_(None),
        ).first()
        if email_session:
            email_session.revoked_at = datetime.utcnow()
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
