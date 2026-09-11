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
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]
    exposure = AnalyticsService.calculate_portfolio_exposure(db, resolved_portfolio, date)
    etf_ids = [UUID(item["etf_id"]) for item in resolved_portfolio]
    risk_metrics = AnalyticsService.calculate_risk_metrics(db, rf_rate, etf_ids=etf_ids)
    top_holdings = AnalyticsService.calculate_portfolio_top_holdings(db, resolved_portfolio, top_n=10, holdings_date=date)

    allocation_overlap = {}
    if len(etf_ids) >= 2:
        allocation_overlap = {
            "sector": AnalyticsService.calculate_allocation_overlap(db, etf_ids, "sector", date),
            "country": AnalyticsService.calculate_allocation_overlap(db, etf_ids, "country", date),
        }

    warnings = list(dict.fromkeys(exposure["analysis_warnings"] + top_holdings["analysis_warnings"]))
    return {**exposure, "risk_metrics": risk_metrics, **top_holdings,
            "allocation_overlap": allocation_overlap, "analysis_warnings": warnings}


@router.post("/alternatives/{etf_id}")
async def find_alternatives(
    etf_id: str,
    request: ExposureRequest,
    top_n: int = 5,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Find ETFs that would reduce holdings overlap when replacing etf_id in the portfolio."""
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]
    target = resolve_etf(db, etf_id)
    return AnalyticsService.suggest_lower_overlap_alternatives(
        db, resolved_portfolio, str(target.id), top_n
    )


@router.post("/pair-suggestions")
async def pair_suggestions(
    request: ExposureRequest,
    include_replacements: bool = False,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """For each overlapping ETF pair in the portfolio, return securities overlap.
    Set include_replacements=true to also search the catalog for the replacement
    with the biggest overlap reduction (slower)."""
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]
    return AnalyticsService.suggest_pair_replacements(db, resolved_portfolio,
                                                       include_replacements=include_replacements)

