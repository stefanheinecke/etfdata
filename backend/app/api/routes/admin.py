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


@router.post("/preview-import")
def preview_import_endpoint(
    symbol: str,
    isin: Optional[str] = None,
    name: Optional[str] = None,
    ter: Optional[float] = None,
    csv_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """
    Preview an ETF import without committing to database.
    Fetches metadata, prices (1-2 years), and calculates performance metrics.
    
    Returns: {
        metadata: {name, isin, ter, currency, provider, domicile, fund_size},
        metrics: {total_return, ytd_return, volatility, sharpe_ratio, max_drawdown, ...},
        prices: [{date, close_price}, ...],  # Last 1-2 years, sampled for charting
        holdings_preview: {count, ...},
        message: "Ready to import"
    }
    """
    from app.services.etf_import_service import (
        _eodhd_token, _fetch_eodhd_meta, _fetch_eodhd_isin, 
        _fetch_eodhd_currency, _upload_performance, upsert_eodhd_prices
    )
    from app.services.performance_calculator import calculate_metrics, get_price_points_for_chart
    from app.schemas import Performance
    
    logs: list = []
    symbol = symbol.strip().upper()
    ticker = symbol.split(".")[0]
    
    try:
        # ---- Metadata ----
        logs.append(f"Preview: fetching metadata for {symbol}...")
        token = _eodhd_token()
        eodhd_meta = {}
        if token:
            eodhd_meta = _fetch_eodhd_meta(symbol, token, logs)
            if not eodhd_meta or not eodhd_meta.get("name"):
                # Try fallback exchanges
                fallback_exchanges = ["LSE", "XETRA", "MI", "PA", "AS"]
                for fb_exch in fallback_exchanges:
                    fb_sym = f"{ticker}.{fb_exch}"
                    eodhd_meta = _fetch_eodhd_meta(fb_sym, token, logs)
                    if eodhd_meta and eodhd_meta.get("name"):
                        break
        
        # Apply overrides
        isin_final = (isin or eodhd_meta.get("isin") or "").strip().upper() or None
        name_final = name or eodhd_meta.get("name") or ticker
        ter_final = ter if ter is not None else eodhd_meta.get("ter")
        currency_final = eodhd_meta.get("currency") or "USD"
        
        metadata = {
            "name": name_final,
            "isin": isin_final,
            "ter": ter_final,
            "currency": currency_final,
            "provider": eodhd_meta.get("provider"),
            "domicile": eodhd_meta.get("domicile"),
            "fund_size": eodhd_meta.get("fund_size"),
            "benchmark": eodhd_meta.get("benchmark"),
            "dividend_policy": eodhd_meta.get("dividend_policy"),
        }
        
        # ---- Fetch Last 2 Years of Prices ----
        logs.append(f"Fetching price history...")
        price_data = []
        if token:
            try:
                import requests
                from datetime import date, timedelta
                
                to_date = date.today()
                from_date = to_date - timedelta(days=730)  # ~2 years
                
                resp = requests.get(
                    f"https://eodhd.com/api/eod/{symbol}",
                    params={
                        "api_token": token,
                        "fmt": "json",
                        "from": from_date.isoformat(),
                        "to": to_date.isoformat(),
                        "period": "d"
                    },
                    timeout=60,
                )
                
                if resp.status_code == 200:
                    rows = resp.json()
                    for row in rows:
                        close = float(row.get("adjusted_close") or row.get("close") or 0)
                        if close > 0:
                            price_data.append({
                                "date": row["date"],
                                "close_price": round(close, 4),
                            })
                    logs.append(f"Fetched {len(price_data)} price records")
                else:
                    logs.append(f"Price fetch failed: HTTP {resp.status_code}")
            except Exception as e:
                logs.append(f"Price fetch error: {e}")
        
        # ---- Calculate Metrics ----
        metrics = {}
        if price_data:
            metrics = calculate_metrics(price_data)
            logs.append(f"Calculated metrics from {metrics['price_count']} prices")
        else:
            logs.append("No price data available for metrics")
        
        # ---- Holdings Preview ----
        holdings_preview = {
            "count": len(eodhd_meta.get("holdings", [])),
            "sample": [
                {
                    "name": h["name"],
                    "weight": h["weight"],
                    "sector": h.get("sector", "—"),
                }
                for h in eodhd_meta.get("holdings", [])[:5]
            ] if eodhd_meta.get("holdings") else []
        }
        
        # ---- Chart Data (sampled for frontend) ----
        chart_data = get_price_points_for_chart(price_data, max_points=250)
        
        return {
            "status": "ok",
            "metadata": metadata,
            "metrics": metrics,
            "prices": chart_data,
            "holdings_preview": holdings_preview,
            "logs": logs,
            "ready_to_import": isin_final is not None and len(price_data) > 10,
            "message": "Preview complete. Ready to import." if len(price_data) > 10 else "Warning: Limited price data"
        }
    
    except Exception as exc:
        logs.append(f"Preview failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


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


@router.delete("/etfs/by-isin/{isin}", status_code=200)
def delete_etf_by_isin(
    isin: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    """Delete an ETF by ISIN and all its holdings, allocations, and performance data."""
    from app.schemas import ETF
    isin_upper = isin.strip().upper()
    etf = db.query(ETF).filter(ETF.isin == isin_upper).first()
    if not etf:
        raise HTTPException(status_code=404, detail=f"ETF with ISIN {isin_upper} not found")
    
    # Delete cascades to holdings, allocations, performance via foreign keys
    db.delete(etf)
    db.commit()
    return {"deleted": True, "isin": isin_upper, "message": f"ETF {isin_upper} and all related data removed"}


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
    from app.schemas import ETF, Holding, Allocation
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
        
        db.flush()  # Flush holdings before creating allocations
        
        # Create allocations from holdings (for donut charts)
        holdings = db.query(Holding).filter(Holding.etf_id == etf.id, Holding.date == holding_date).all()
        total_weight = sum(float(h.weight) for h in holdings if h.weight)
        
        # Country allocations
        country_totals = {}
        for holding in holdings:
            if holding.country and holding.weight:
                country_totals[holding.country] = country_totals.get(holding.country, 0.0) + float(holding.weight)
        
        for country, weight in country_totals.items():
            if weight > 0:
                pct = round(weight / total_weight * 100, 4) if total_weight > 0 else 0
                db.add(Allocation(etf_id=etf.id, date=holding_date, type="country", bucket=country, weight=pct))
        
        # Sector allocations
        sector_totals = {}
        for holding in holdings:
            if holding.sector and holding.weight:
                sector_totals[holding.sector] = sector_totals.get(holding.sector, 0.0) + float(holding.weight)
        
        for sector, weight in sector_totals.items():
            if weight > 0:
                pct = round(weight / total_weight * 100, 4) if total_weight > 0 else 0
                db.add(Allocation(etf_id=etf.id, date=holding_date, type="sector", bucket=sector, weight=pct))
        
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
