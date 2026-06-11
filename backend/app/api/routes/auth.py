"""
Public auth routes — no admin secret required.
"""
import requests as _requests

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import create_api_key
from app.core.email import send_api_key_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-key")
def request_key(
    email: str,
    db: Session = Depends(get_db),
):
    """
    Self-service API key creation.
    Anyone can request a key by providing their email address.
    The key is delivered by email and never returned in the response.
    """
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")

    email = email.strip().lower()[:255]
    name = email.split("@")[0][:100]

    raw_key, db_key = create_api_key(db, name=name, email=email)

    try:
        send_api_key_email(to_email=email, api_key=raw_key)
    except RuntimeError as exc:
        db.delete(db_key)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc))
    except _requests.HTTPError as exc:
        db.delete(db_key)
        db.commit()
        raise HTTPException(status_code=503, detail=f"Email delivery failed: {exc.response.text if exc.response else exc}")

    return {
        "message": f"Your API key has been sent to {email}. Check your inbox.",
        "email": email,
        "rate_limit_per_minute": db_key.rate_limit_per_minute,
    }
