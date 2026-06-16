from datetime import date as date_type
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import APIKey
from app.models import ExposureRequest, RiskMetricsRequest
from app.services.analytics_service import AnalyticsService
from app.api.utils import resolve_etf

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.post("/exposure")
async def calculate_exposure(
    request: ExposureRequest,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]
    result = AnalyticsService.calculate_portfolio_exposure(db, resolved_portfolio, date)
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

@router.post("/risk-metrics")
async def get_portfolio_risk_metrics(
    request: RiskMetricsRequest,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Return risk metrics for a specific list of ETFs (by ticker or UUID).
    Useful for comparing multiple ETFs in a portfolio side by side.
    rf_rate: annual risk-free rate as a decimal (default 0.04 = 4%).
    """
    resolved_ids = [resolve_etf(db, ref).id for ref in request.etf_ids]
    return AnalyticsService.calculate_risk_metrics(db, rf_rate, etf_ids=resolved_ids)
