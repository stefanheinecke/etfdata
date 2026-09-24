from datetime import date as date_type
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import ETF, APIKey, Holding
from app.models import ETFCreate, ETFResponse
from app.api.utils import resolve_etf
from app.services.fx_service import get_latest_rates_map, get_latest_rate

router = APIRouter(prefix="/etfs", tags=["etfs"])

@router.get("/count")
async def get_etf_count(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Total number of tracked ETFs. Used by the marketing homepage's live counter."""
    return {"total": db.query(ETF).count()}


@router.get("", response_model=List[ETFResponse])
async def list_etfs(
    skip: int = 0,
    limit: int = 50,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    query = db.query(ETF)
    if provider:
        query = query.filter(ETF.provider == provider)
    etfs = query.order_by(ETF.isin).offset(skip).limit(limit).all()

    holdings_counts = {}
    if etfs:
        latest = (
            db.query(Holding.etf_id, func.max(Holding.date).label("date"))
            .filter(Holding.etf_id.in_([e.id for e in etfs]))
            .group_by(Holding.etf_id).subquery()
        )
        holdings_counts = dict(
            db.query(Holding.etf_id, func.count(Holding.id))
            .join(latest, (Holding.etf_id == latest.c.etf_id) & (Holding.date == latest.c.date))
            .group_by(Holding.etf_id).all()
        )

    rates = get_latest_rates_map(db, {e.currency for e in etfs if e.currency})
    results = []
    for e in etfs:
        resp = ETFResponse.model_validate(e)
        resp.holdings_count = holdings_counts.get(e.id, 0)
        rate = rates.get((e.currency or "").strip().upper()[:3])
        resp.fund_size_usd = round(e.fund_size * rate) if (e.fund_size and rate) else None
        results.append(resp)
    return results

@router.get("/risk-metrics")
async def get_etf_risk_metrics(
    isins: Optional[str] = None,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Return risk metrics for one or more ETFs. isins = comma-separated ISINs or UUIDs."""
    from app.services.analytics_service import AnalyticsService
    from uuid import UUID
    etf_ids = None
    if isins:
        isin_list = [t.strip() for t in isins.split(",") if t.strip()]
        resolved = [resolve_etf(db, t) for t in isin_list]
        etf_ids = [etf.id for etf in resolved]
    return AnalyticsService.calculate_risk_metrics(db, rf_rate, etf_ids=etf_ids)

@router.get("/{etf_id}", response_model=ETFResponse)
async def get_etf(
    etf_id: str,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    etf = resolve_etf(db, etf_id)
    resp = ETFResponse.model_validate(etf)
    rate = get_latest_rate(db, etf.currency)
    resp.fund_size_usd = round(etf.fund_size * rate) if (etf.fund_size and rate) else None
    return resp

@router.get("/{etf_id}/holdings")
async def get_holdings(
    etf_id: str,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Holding

    etf = resolve_etf(db, etf_id)

    query = db.query(Holding).filter(Holding.etf_id == etf.id)

    if date:
        query = query.filter(Holding.date == date)
    else:
        latest_date = db.query(func.max(Holding.date)).filter(
            Holding.etf_id == etf.id
        ).scalar()
        if latest_date:
            query = query.filter(Holding.date == latest_date)

    holdings = query.all()
    return [h for h in holdings]

@router.get("/{etf_id}/allocations")
async def get_allocations(
    etf_id: str,
    type: Optional[str] = None,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Allocation
    from app.services.analytics_service import _allocation_snapshot

    etf = resolve_etf(db, etf_id)

    query = db.query(Allocation).filter(Allocation.etf_id == etf.id)

    if type:
        query = query.filter(Allocation.type == type)

    if date:
        query = query.filter(Allocation.date == date)
    else:
        latest_date = db.query(func.max(Allocation.date)).filter(
            Allocation.etf_id == etf.id
        ).scalar()
        if latest_date:
            query = query.filter(Allocation.date == latest_date)

    allocations = query.all()
    if allocations:
        return allocations

    # No explicit Allocation rows for this ETF (e.g. its holdings were imported
    # via the iShares CSV path, which only writes Holding rows — see
    # holdings_db_import.py). Derive the same country/sector/currency
    # breakdown from holdings, reusing the fallback analytics/scoring already
    # rely on via _allocation_snapshot, instead of showing an empty tab.
    derived = []
    for alloc_type in ([type] if type else ["country", "sector", "currency"]):
        snapshot = _allocation_snapshot(db, etf.id, alloc_type, date)
        if snapshot["status"] != "available":
            continue
        for bucket, weight in snapshot["weights"].items():
            derived.append({"type": alloc_type, "bucket": bucket, "weight": round(weight, 4),
                            "date": snapshot["as_of"], "etf_id": str(etf.id)})
    return derived

@router.get("/{etf_id}/performance")
async def get_etf_performance(
    etf_id: str,
    from_date: Optional[date_type] = None,
    to_date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Performance
    etf = resolve_etf(db, etf_id)
    query = db.query(Performance).filter(Performance.etf_id == etf.id)
    if from_date:
        query = query.filter(Performance.date >= from_date)
    if to_date:
        query = query.filter(Performance.date <= to_date)
    rows = query.order_by(Performance.date.desc()).limit(1000).all()
    return [{"date": str(r.date), "close_price": r.close_price, "nav": r.nav, "currency": r.currency, "dividend": r.dividend} for r in rows]


@router.get("/{etf_id}/explain")
async def get_etf_explanation(
    etf_id: str,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """
    AI-generated plain-English explanation of this ETF, grounded strictly in
    its own holdings/allocation/score data already in the database (no
    external knowledge about the fund or issuer is used). Cached per ETF and
    never regenerated once created. Generating it for the first time (cache
    miss) triggers a paid LLM call, so it requires a personal API key — the
    public demo key can only read explanations that are already cached.
    """
    from app.services.etf_explainer import generate_etf_explanation, _load_cached
    is_demo = getattr(api_key, "name", None) == "__demo__"
    etf = resolve_etf(db, etf_id)
    if is_demo:
        cached = _load_cached(db, etf.id)
        if cached is None:
            raise HTTPException(status_code=403, detail="No cached explanation yet for this ETF — generating a new one requires a personal API key")
        return {"text": cached.text, "model": cached.model, "generated_at": cached.generated_at.isoformat(), "cached": True}
    try:
        return generate_etf_explanation(db, etf)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
