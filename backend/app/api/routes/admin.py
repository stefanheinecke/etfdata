import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from typing import List, Optional
from app.db.database import get_db
from app.core.auth import create_api_key
from app.services.seed import seed_database
from app.services.ishares_import import import_ishares, ISHARES_ETFS

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_secret(x_admin_secret: str = Header(None)):
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_admin_secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/init-db")
def init_db_endpoint(_: None = Depends(verify_admin_secret)):
    from app.db.database import init_db
    init_db()
    return {"status": "ok", "message": "Database tables created"}


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


@router.post("/reset")
def reset(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    from app.schemas import ETF, Holding, Allocation, Performance, APIKey as APIKeyModel
    from app.services.seed import seed_database
    db.query(Holding).delete()
    db.query(Allocation).delete()
    db.query(Performance).delete()
    db.query(ETF).delete()
    db.commit()
    result = seed_database(db)
    return {"reset": True, "seeded": result}


@router.post("/seed")
def seed(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    result = seed_database(db)
    return {"seeded": result}


@router.get("/import-ishares/etfs")
def list_ishares_etfs(_: None = Depends(verify_admin_secret)):
    """List the 10 iShares ETFs available for import."""
    return [
        {"ticker": e["ticker"], "name": e["name"], "product_id": e["product_id"]}
        for e in ISHARES_ETFS
    ]


@router.post("/import-ishares")
def import_ishares_endpoint(
    tickers: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """
    Download real holdings data from iShares.com and import into the database.
    Pass ?tickers=IVV&tickers=EEM to import a subset, or omit to import all 10.
    """
    result = import_ishares(db, tickers=tickers)
    return result
