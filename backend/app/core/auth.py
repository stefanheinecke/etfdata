import hashlib
import secrets
from types import SimpleNamespace
from datetime import datetime
from fastapi import HTTPException, Header, Cookie, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas import APIKey, GoogleAccount, WebSession

# Public demo key — read-only, full catalog access, low rate limit
DEMO_API_KEY = "demo"

def generate_api_key():
    return secrets.token_urlsafe(48)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def get_google_account_for_session(session_token: str, db: Session):
    if not session_token:
        return None

    session = db.query(WebSession).filter(
        WebSession.token_hash == hash_api_key(session_token),
        WebSession.revoked_at.is_(None),
        WebSession.expires_at > datetime.utcnow(),
    ).first()
    if not session:
        return None

    return db.query(GoogleAccount).filter(
        GoogleAccount.id == session.google_account_id
    ).first()

async def verify_api_key(
    x_api_key: str = Header(None),
    web_session: str = Cookie(None),
    db: Session = Depends(get_db)
) -> APIKey:
    account = get_google_account_for_session(web_session, db)
    if account:
        return SimpleNamespace(
            name=account.name or account.email.split("@")[0],
            id=None,
            is_active=True,
            rate_limit_per_minute=60,
            email=account.email,
            key=None,
        )

    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key required")

    if x_api_key == DEMO_API_KEY:
        return SimpleNamespace(
            name="__demo__", id=None, is_active=True,
            rate_limit_per_minute=10, email=None, key=None
        )

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

def create_api_key(db: Session, name: str, rate_limit_per_minute: int = 60, email: str = None):
    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)

    db_key = APIKey(
        key=hashed_key,
        name=name,
        email=email,
        rate_limit_per_minute=rate_limit_per_minute
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    return raw_key, db_key
