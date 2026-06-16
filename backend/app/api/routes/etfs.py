from datetime import date as date_type
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import ETF, APIKey
from app.models import ETFCreate, ETFResponse
from app.api.utils import resolve_etf

router = APIRouter(prefix="/etfs", tags=["etfs"])

def _is_demo(api_key) -> bool:
    return getattr(api_key, 'name', '') == '__demo__'

@router.get("", response_model=List[ETFResponse])
async def list_etfs(
    skip: int = 0,
    limit: int = 50,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    query = db.query(ETF)
    if _is_demo(api_key):
        query = query.filter(ETF.ticker == "SWDA")
    elif provider:
        query = query.filter(ETF.provider == provider)
    return query.offset(skip).limit(limit).all()

@router.get("/risk-metrics")
async def get_etf_risk_metrics(
    tickers: Optional[str] = None,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Return risk metrics for one or more ETFs. tickers = comma-separated tickers or UUIDs."""
    from app.services.analytics_service import AnalyticsService
    from uuid import UUID
    etf_ids = None
    if tickers:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        if _is_demo(api_key):
            if any(t.upper() != "SWDA" for t in ticker_list):
                raise HTTPException(status_code=403, detail="Demo key only allows access to SWDA ETF")
        resolved = [resolve_etf(db, t) for t in ticker_list]
        etf_ids = [etf.id for etf in resolved]
    elif _is_demo(api_key):
        swda = db.query(ETF).filter(ETF.ticker == "SWDA").first()
        etf_ids = [swda.id] if swda else []
    return AnalyticsService.calculate_risk_metrics(db, rf_rate, etf_ids=etf_ids)

@router.get("/{etf_id}", response_model=ETFResponse)
async def get_etf(
    etf_id: str,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    etf = resolve_etf(db, etf_id)
    if _is_demo(api_key) and etf.ticker != "SWDA":
        raise HTTPException(status_code=403, detail="Demo key only allows access to SWDA ETF")
    return etf

@router.get("/{etf_id}/holdings")
async def get_holdings(
    etf_id: str,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Holding

    etf = resolve_etf(db, etf_id)
    if _is_demo(api_key) and etf.ticker != "SWDA":
        raise HTTPException(status_code=403, detail="Demo key only allows access to SWDA ETF")

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

    etf = resolve_etf(db, etf_id)
    if _is_demo(api_key) and etf.ticker != "SWDA":
        raise HTTPException(status_code=403, detail="Demo key only allows access to SWDA ETF")

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
    return [a for a in allocations]

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
    if _is_demo(api_key) and etf.ticker != "SWDA":
        raise HTTPException(status_code=403, detail="Demo key only allows access to SWDA ETF")
    query = db.query(Performance).filter(Performance.etf_id == etf.id)
    if from_date:
        query = query.filter(Performance.date >= from_date)
    if to_date:
        query = query.filter(Performance.date <= to_date)
    rows = query.order_by(Performance.date.desc()).limit(1000).all()
    return [{"date": str(r.date), "close_price": r.close_price, "nav": r.nav, "currency": r.currency, "dividend": r.dividend} for r in rows]
