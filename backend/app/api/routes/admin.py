import os
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID

from typing import List, Optional
from app.db.database import get_db
from app.core.auth import create_api_key
from app.services.ishares_import import import_ishares, ISHARES_ETFS

router = APIRouter(prefix="/admin", tags=["admin"])


class ImportRequest(BaseModel):
    tickers: Optional[List[str]] = None


def verify_admin_secret(x_admin_secret: str = Header(None)):
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_admin_secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.get("/verify")
def verify_endpoint(_: None = Depends(verify_admin_secret)):
    return {"status": "ok"}


@router.post("/import-etf")
def import_etf_endpoint(
    ticker: str,
    isin: str,
    name: Optional[str] = None,
    ter: Optional[float] = None,
    csv_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Register or update an iShares ETF and upload its holdings CSV."""
    from app.services.etf_import_service import import_etf
    csv_bytes = csv_file.file.read() if csv_file else None
    logs: list = []
    try:
        result = import_etf(ticker, isin, csv_bytes, db, logs, name_override=name, ter_override=ter)
        return {"status": "ok", "logs": logs, **result}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@router.post("/init-db")
def init_db_endpoint(_: None = Depends(verify_admin_secret)):
    from app.db.database import init_db
    init_db()
    return {"status": "ok", "message": "Database tables created"}


@router.post("/api-keys")
def create_key(
    name: str,
    email: str,
    rate_limit_per_minute: int = 60,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    raw_key, db_key = create_api_key(db, name=name, rate_limit_per_minute=rate_limit_per_minute, email=email)
    return {
        "api_key": raw_key,
        "name": db_key.name,
        "email": db_key.email,
        "id": str(db_key.id),
        "rate_limit_per_minute": db_key.rate_limit_per_minute,
    }


@router.get("/request-logs")
def get_request_logs(
    limit: int = 100,
    offset: int = 0,
    api_key_name: Optional[str] = None,
    email: Optional[str] = None,
    path: Optional[str] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Return paginated request logs, newest first. Filter by api_key_name, email, or path prefix."""
    from app.schemas import RequestLog
    q = db.query(RequestLog)
    if api_key_name:
        q = q.filter(RequestLog.api_key_name.ilike(f"%{api_key_name}%"))
    if email:
        q = q.filter(RequestLog.email.ilike(f"%{email}%"))
    if path:
        q = q.filter(RequestLog.path.ilike(f"{path}%"))
    total = q.count()
    rows = q.order_by(RequestLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": r.id,
                "api_key_name": r.api_key_name,
                "email": r.email,
                "method": r.method,
                "path": r.path,
                "query_string": r.query_string,
                "request_body": r.request_body,
                "status_code": r.status_code,
                "response_time_ms": r.response_time_ms,
                "client_ip": r.client_ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/reset")
def reset(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Delete all ETF data (holdings, allocations, performance, ETFs) from the database."""
    from app.schemas import ETF, Holding, Allocation, Performance
    db.query(Holding).delete()
    db.query(Allocation).delete()
    db.query(Performance).delete()
    db.query(ETF).delete()
    db.commit()
    return {"reset": True, "message": "All ETF data deleted. Run /admin/import-ishares to import real data."}


@router.get("/import-ishares/etfs")
def list_ishares_etfs(_: None = Depends(verify_admin_secret)):
    """List the 13 iShares ETFs available for import."""
    return [
        {"ticker": e["ticker"], "name": e["name"], "isin": e["isin"], "yf_symbol": e["yf_symbol"]}
        for e in ISHARES_ETFS
    ]


@router.post("/import-ishares")
def import_ishares_endpoint(
    body: ImportRequest = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """
    Download real holdings data from iShares.com and import into the database.
    Provide {"tickers": ["IVV", "EEM"]} to import a subset, or omit / send {} to import all.
    """
    tickers = body.tickers if body else None
    result = import_ishares(db, tickers=tickers)
    return result


@router.delete("/etfs/{etf_id}", status_code=204)
def delete_etf(
    etf_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Delete a single ETF and all its holdings, allocations and performance data."""
    from app.schemas import ETF
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")
    db.delete(etf)
    db.commit()


@router.delete("/etfs", status_code=200)
def delete_etfs(
    etf_ids: List[UUID],
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Delete multiple ETFs by ID list. Returns count of deleted records."""
    from app.schemas import ETF
    deleted = 0
    for etf_id in etf_ids:
        etf = db.query(ETF).filter(ETF.id == etf_id).first()
        if etf:
            db.delete(etf)
            deleted += 1
    db.commit()
    return {"deleted": deleted}
