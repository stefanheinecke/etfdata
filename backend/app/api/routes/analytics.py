from datetime import date as date_type
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import APIKey
from app.models import ExposureRequest
from app.services.analytics_service import AnalyticsService
from app.api.utils import resolve_etf

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.post("/exposure")
async def calculate_exposure(
    request: ExposureRequest,
    rf_rate: float = 0.04,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Portfolio exposure: sector/country/currency breakdown plus per-ETF risk metrics.
    rf_rate: annual risk-free rate as a decimal (default 0.04 = 4%).
    """
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]
    exposure = AnalyticsService.calculate_portfolio_exposure(db, resolved_portfolio, date)
    etf_ids = [UUID(item["etf_id"]) for item in resolved_portfolio]
    risk_metrics = AnalyticsService.calculate_risk_metrics(db, rf_rate, etf_ids=etf_ids)
    return {**exposure, "risk_metrics": risk_metrics}
