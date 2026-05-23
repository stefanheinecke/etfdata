import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import create_api_key
from app.services.seed import seed_database

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_secret(x_admin_secret: str = Header(None)):
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_admin_secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/api-keys")
def create_key(
    name: str,
    rate_limit_per_minute: int = 60,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    raw_key, db_key = create_api_key(db, name=name, rate_limit_per_minute=rate_limit_per_minute)
    return {
        "api_key": raw_key,
        "name": db_key.name,
        "id": str(db_key.id),
        "rate_limit_per_minute": db_key.rate_limit_per_minute,
    }


@router.post("/seed")
def seed(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    result = seed_database(db)
    return {"seeded": result}
