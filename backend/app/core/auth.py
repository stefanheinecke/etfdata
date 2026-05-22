import hashlib
import secrets
from datetime import datetime
from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas import APIKey

def generate_api_key():
    return secrets.token_urlsafe(48)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

async def verify_api_key(
    x_api_key: str = Header(None),
    db: Session = Depends(get_db)
) -> APIKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key required")

    hashed_key = hash_api_key(x_api_key)
    api_key = db.query(APIKey).filter(
        APIKey.key == hashed_key,
        APIKey.is_active == True
    ).first()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API Key expired")

    api_key.last_used_at = datetime.utcnow()
    db.commit()

    return api_key

def create_api_key(db: Session, name: str, rate_limit_per_minute: int = 60):
    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)

    db_key = APIKey(
        key=hashed_key,
        name=name,
        rate_limit_per_minute=rate_limit_per_minute
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    return raw_key, db_key
