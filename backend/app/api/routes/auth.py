"""
Public auth routes — no admin secret required.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import create_api_key

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-key")
def request_key(
    name: str,
    email: str,
    db: Session = Depends(get_db),
):
    """
    Self-service API key creation.
    Anyone can request a key by providing a name and email address.
    """
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")
    if not name or not name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")

    raw_key, db_key = create_api_key(
        db,
        name=name.strip()[:100],
        email=email.strip().lower()[:255],
    )
    return {
        "api_key": raw_key,
        "name": db_key.name,
        "email": db_key.email,
        "rate_limit_per_minute": db_key.rate_limit_per_minute,
        "message": "Keep your API key safe — it won't be shown again.",
    }
