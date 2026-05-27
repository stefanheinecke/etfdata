from uuid import UUID
from datetime import date as date_type
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import APIKey
from app.models import OverlapRequest, ExposureRequest
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.post("/overlap")
async def calculate_overlap(
    request: OverlapRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    result = AnalyticsService.calculate_overlap(db, request.etf_ids, request.date)
    return result

@router.get("/overlap/{etf_a}/{etf_b}")
async def pairwise_overlap(
    etf_a: UUID,
    etf_b: UUID,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    result = AnalyticsService.calculate_overlap(db, [etf_a, etf_b], date)
    return result

@router.post("/exposure")
async def calculate_exposure(
    request: ExposureRequest,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    result = AnalyticsService.calculate_portfolio_exposure(db, request.portfolio, date)
    return result

@router.get("/similar/{etf_id}")
async def find_similar(
    etf_id: UUID,
    top_n: int = 5,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    result = AnalyticsService.find_similar_etfs(db, etf_id, top_n)
    return result

@router.get("/risk-metrics")
async def get_risk_metrics(
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Return volatility, Sharpe ratio, max drawdown, and HHI for all ETFs.
    rf_rate: annual risk-free rate as a decimal (default 0.04 = 4%).
    """
    return AnalyticsService.calculate_risk_metrics(db, rf_rate)
