from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.schemas import ETF


def resolve_etf(db: Session, etf_ref: str) -> ETF:
    """Resolve an ETF by UUID string or ticker symbol (case-insensitive).

    Tries UUID parse first; falls back to ticker lookup.
    Raises HTTP 404 if not found.
    """
    etf = None
    try:
        uid = UUID(str(etf_ref))
        etf = db.query(ETF).filter(ETF.id == uid).first()
    except (ValueError, AttributeError):
        pass

    if etf is None:
        etf = db.query(ETF).filter(ETF.ticker == str(etf_ref).upper()).first()

    if etf is None:
        raise HTTPException(status_code=404, detail=f"ETF '{etf_ref}' not found")

    return etf
