import os
import threading
from datetime import date as date_type
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from typing import List, Optional
from app.db.database import get_db, SessionLocal
from app.core.auth import create_api_key
from app.services.ishares_import import import_ishares, ISHARES_ETFS

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# In-memory job store for async price refresh progress tracking
# ---------------------------------------------------------------------------
_refresh_jobs: dict[str, dict] = {}


class ImportRequest(BaseModel):
    tickers: Optional[List[str]] = None


class ETFUpdateBody(BaseModel):
    name: Optional[str] = None
    isin: Optional[str] = None
    ter: Optional[float] = None
    currency: Optional[str] = None
    benchmark: Optional[str] = None
    provider: Optional[str] = None
    domicile: Optional[str] = None
    fund_size: Optional[int] = None
    dividend_policy: Optional[str] = None
    replication_method: Optional[str] = None


class HoldingUpdateBody(BaseModel):
    instrument_isin: Optional[str] = None
    instrument_name: Optional[str] = None
    weight: Optional[float] = None
    sector: Optional[str] = None
    country: Optional[str] = None


class HoldingCreateBody(BaseModel):
    instrument_isin: Optional[str] = None  # May not be available in all factsheets
    instrument_name: str
    weight: float
    sector: Optional[str] = None
    country: Optional[str] = None
    date: Optional[date_type] = None


def verify_admin_secret(x_admin_secret: str = Header(None)):
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_admin_secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.get("/verify")
def verify_endpoint(_: None = Depends(verify_admin_secret)):
    return {"status": "ok"}


@router.post("/refresh-prices")
def refresh_prices_endpoint(_: None = Depends(verify_admin_secret)):
    """
    Start an async price refresh job. Returns a job_id immediately.
    Poll GET /admin/refresh-prices/status/{job_id} for live progress.
    """
    from app.services.ishares_import import refresh_daily_prices

    job_id = str(uuid4())
    _refresh_jobs[job_id] = {
        "status": "running",
        "done": 0,
        "total": 0,
        "current_ticker": "",
        "total_rows_upserted": 0,
        "etfs": [],
        "errors": [],
    }

    def _run():
        db = SessionLocal()
        try:
            def _progress(done: int, total: int, ticker: str):
                _refresh_jobs[job_id].update({"done": done, "total": total, "current_ticker": ticker})

            result = refresh_daily_prices(db, progress_cb=_progress)
            _refresh_jobs[job_id].update({
                "status": "done",
                "done": result.get("total_etfs", 0),
                "total": result.get("total_etfs", 0),
                "current_ticker": "",
                "total_rows_upserted": result["total_rows_upserted"],
                "etfs": result["etfs"],
                "errors": result["errors"],
            })
        except Exception as exc:
            _refresh_jobs[job_id].update({"status": "error", "errors": [str(exc)]})
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.get("/refresh-prices/status/{job_id}")
def refresh_prices_status(job_id: str, _: None = Depends(verify_admin_secret)):
    """Poll for progress of a running or completed refresh job."""
    job = _refresh_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return job


@router.post("/backfill-eodhd-symbols")
def backfill_eodhd_symbols(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """
    One-time migration: populate etf.listings['eodhd_symbol'] for ETFs that were
    imported before this field was tracked. Derives the symbol from the ETF ticker
    and the exchange suffix inferred from their price history currency.
    After running this, 'Refresh Prices' will use EODHD for all ETFs.
    """
    from app.schemas import ETF as ETFModel
    from app.services.ishares_import import _YF_PERF_SYMBOL, _eodhd_symbol_for_etf
    import os, requests as req_lib

    token = os.getenv("EODHD_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="EODHD_TOKEN not set — cannot verify symbols.")

    etfs = db.query(ETFModel).order_by(ETFModel.isin).all()
    updated = []
    skipped = []

    for etf in etfs:
        # Already has a symbol stored
        if etf.listings and etf.listings.get("eodhd_symbol"):
            skipped.append({"isin": etf.isin, "reason": "already set",
                            "eodhd_symbol": etf.listings["eodhd_symbol"]})
            continue

        # Try to derive from catalogue yfinance symbol - use ISIN if available
        candidate = None
        if etf.listings and etf.listings.get("eodhd_symbol"):
            candidate = etf.listings["eodhd_symbol"]
        else:
            # Guess based on currency: USD→.US, EUR→.AS, GBP→.LSE (best effort)
            # Without ticker, we use ISIN-based logic or currency hints
            suffix = {"USD": ".US", "GBP": ".LSE", "EUR": ".AS"}.get(etf.currency or "", ".AS")
            # Use provider name + ISIN for better matching
            if etf.provider:
                candidate = f"{etf.provider}_{etf.isin}{suffix}"
            else:
                candidate = f"{etf.isin}{suffix}"

        # Verify the candidate actually returns data from EODHD
        try:
            resp = req_lib.get(
                f"https://eodhd.com/api/eod/{candidate}",
                params={"api_token": token, "fmt": "json", "from": "2026-01-01",
                        "to": "2026-01-31", "period": "d"},
                timeout=15,
            )
            if resp.status_code == 200 and resp.json():
                etf.listings = {**(etf.listings or {}), "eodhd_symbol": candidate}
                db.commit()
                updated.append({"isin": etf.isin, "eodhd_symbol": candidate})
            else:
                skipped.append({"isin": etf.isin, "reason": f"HTTP {resp.status_code} or empty",
                                "candidate": candidate})
        except Exception as exc:
            skipped.append({"isin": etf.isin, "reason": str(exc), "candidate": candidate})

    return {"updated": updated, "skipped": skipped}


@router.post("/import-etf")
def import_etf_endpoint(
    symbol: str,
    isin: Optional[str] = None,
    name: Optional[str] = None,
    ter: Optional[float] = None,
    csv_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Register or update an ETF by EODHD symbol (e.g. 'EIMI.SW', 'SWDA.LSE').
    All metadata is fetched from EODHD. Provide isin only if EODHD does not return it."""
    from app.services.etf_import_service import import_etf
    csv_bytes = csv_file.file.read() if csv_file else None
    logs: list = []
    try:
        result = import_etf(symbol, csv_bytes, db, logs, isin_override=isin, name_override=name, ter_override=ter)
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
    Provide {"isins": ["IE00B4L5Y983", "IE00B6R52259"]} to import a subset, or omit / send {} to import all.
    
    Note: For now, this endpoint still expects the old ticker format for backward compatibility.
    Update the request body to use ISINs instead of tickers.
    """
    # Support both 'tickers' (for backward compatibility) and 'isins' in the request
    tickers = getattr(body, 'tickers', None) or getattr(body, 'isins', None) if body else None
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


@router.patch("/etfs/{etf_id}")
def update_etf_metadata(
    etf_id: UUID,
    body: ETFUpdateBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Update ETF metadata fields. Only provided fields are changed."""
    from decimal import Decimal
    from app.schemas import ETF
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")
    for field, value in body.dict(exclude_none=True).items():
        if field == "ter" and value is not None:
            setattr(etf, field, Decimal(str(value)))
        elif field == "isin" and value:
            setattr(etf, field, value.strip().upper() or None)
        elif field == "domicile" and value:
            setattr(etf, field, value.strip().upper()[:2])
        elif field == "currency" and value:
            setattr(etf, field, value.strip().upper()[:3])
        else:
            setattr(etf, field, value or None)
    db.commit()
    db.refresh(etf)
    return {
        "id": str(etf.id), "name": etf.name,
        "isin": etf.isin, "ter": float(etf.ter) if etf.ter else None,
        "currency": etf.currency, "provider": etf.provider,
        "domicile": etf.domicile, "fund_size": etf.fund_size,
        "benchmark": etf.benchmark, "dividend_policy": etf.dividend_policy,
        "replication_method": etf.replication_method,
    }


def _holding_dict(h) -> dict:
    return {
        "id": str(h.id), "etf_id": str(h.etf_id), "date": h.date.isoformat(),
        "instrument_isin": h.instrument_isin, "instrument_name": h.instrument_name,
        "weight": float(h.weight), "sector": h.sector, "country": h.country,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


@router.patch("/etfs/{etf_id}/holdings/{holding_id}")
def update_holding(
    etf_id: UUID,
    holding_id: UUID,
    body: HoldingUpdateBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Update a single holding row."""
    from decimal import Decimal
    from app.schemas import Holding
    h = db.query(Holding).filter(Holding.id == holding_id, Holding.etf_id == etf_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    for field, value in body.dict(exclude_none=True).items():
        if field == "weight":
            setattr(h, field, Decimal(str(value)))
        elif field in ("country", "instrument_isin"):
            setattr(h, field, (value or "").strip().upper())
        else:
            setattr(h, field, value)
    db.commit()
    db.refresh(h)
    return _holding_dict(h)


@router.delete("/etfs/{etf_id}/holdings/{holding_id}", status_code=204)
def delete_holding(
    etf_id: UUID,
    holding_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Delete a single holding row."""
    from app.schemas import Holding
    h = db.query(Holding).filter(Holding.id == holding_id, Holding.etf_id == etf_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()


@router.post("/etfs/{etf_id}/holdings", status_code=201)
def add_holding(
    etf_id: UUID,
    body: HoldingCreateBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Add a new holding row to an ETF."""
    from decimal import Decimal
    from app.schemas import ETF, Holding
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")
    h = Holding(
        etf_id=etf_id,
        date=body.date or date_type.today(),
        instrument_isin=(body.instrument_isin or "").strip().upper()[:12],
        instrument_name=(body.instrument_name or "")[:255],
        weight=Decimal(str(body.weight)),
        sector=body.sector or None,
        country=(body.country or "").strip().upper()[:2] or None,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return _holding_dict(h)


# ───────────────────────────────────────────────────────────────────────────
# ETF Import from Factsheet PDF
# ───────────────────────────────────────────────────────────────────────────

@router.post("/etf/upload-factsheet")
async def upload_factsheet(
    file: UploadFile = File(...),
):
    """Upload an ETF factsheet PDF for data extraction."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.services.pdf_extraction import PDFExtractionService
        
        if not file.filename.endswith('.pdf'):
            return {"status": "error", "message": "Only PDF files are supported"}
        
        pdf_bytes = await file.read()
        result = PDFExtractionService.extract_from_pdf(pdf_bytes)
        return result
    except Exception as e:
        logger.exception(f"PDF upload error: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to process PDF: {str(e)}",
            "error_type": type(e).__name__
        }


class ETFImportRequest(BaseModel):
    metadata: dict  # Must include 'isin' as the unique identifier
    holdings: List[dict]
    date: Optional[date_type] = None


@router.post("/etf/import-data")
async def import_etf_data(
    request: ETFImportRequest,
    db: Session = Depends(get_db),
):
    """Import extracted ETF data into the database."""
    from decimal import Decimal
    from app.schemas import ETF, Holding
    from datetime import date as date_type
    
    isin = (request.metadata.get('isin') or '').strip().upper()
    
    if not isin:
        raise HTTPException(status_code=400, detail="ISIN is required in metadata")
    
    # Check if ETF already exists
    existing_etf = db.query(ETF).filter(ETF.isin == isin).first()
    if existing_etf:
        raise HTTPException(status_code=409, detail=f"ETF with ISIN {isin} already exists")
    
    try:
        # Create ETF
        domicile = request.metadata.get('domicile')
        etf = ETF(
            isin=isin,
            name=request.metadata.get('name', isin),
            provider=request.metadata.get('provider'),
            domicile=domicile.strip().upper()[:2] if domicile else None,
            ter=Decimal(str(request.metadata.get('ter', 0))) if request.metadata.get('ter') else None,
            fund_size=request.metadata.get('fund_size'),
            benchmark=request.metadata.get('benchmark'),
            currency=request.metadata.get('currency', 'USD'),
        )
        db.add(etf)
        db.flush()  # Get the ETF ID
        
        # Add holdings
        holding_date = request.date or date_type.today()
        for holding_data in request.holdings:
            holding = Holding(
                etf_id=etf.id,
                date=holding_date,
                instrument_isin=(holding_data.get('instrument_isin') or '').strip().upper()[:12] or None,
                instrument_name=(holding_data.get('instrument_name') or '')[:255],
                weight=Decimal(str(holding_data.get('weight', 0))),
                sector=holding_data.get('sector'),
                country=(holding_data.get('country') or '').strip().upper()[:2] or None,
            )
            db.add(holding)
        
        db.commit()
        db.refresh(etf)
        
        return {
            "status": "success",
            "etf": {
                "id": str(etf.id),
                "isin": etf.isin,
                "name": etf.name,
                "provider": etf.provider,
                "holdings_count": len(request.holdings),
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to import ETF: {str(e)}")
