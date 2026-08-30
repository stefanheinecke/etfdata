from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import APIKey, ETF
from app.models import ExposureRequest
from app.api.utils import resolve_etf
from app.services.scoring_service import compute_goetf_scores, compute_portfolio_score

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/etfs")
async def get_etf_scores(
    isins: Optional[str] = None,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
):
    """
    GoETF Score for all ETFs (or a comma-separated ISIN subset).
    Each ETF receives a 1-10 quality score based on seven equally weighted
    return, risk, diversification, and cost components.
    """
    etf_ids = None

    if isins:
        isin_list = [t.strip().upper() for t in isins.split(",") if t.strip()]
        resolved = [resolve_etf(db, t) for t in isin_list]
        etf_ids = [e.id for e in resolved]

    return compute_goetf_scores(db, rf_annual=rf_rate, etf_ids=etf_ids)


@router.post("/portfolio")
async def get_portfolio_score(
    request: ExposureRequest,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
):
    """
    GoETF Portfolio Score.

    Computes a composite portfolio-level GoETF Score (1–10) based on:
    - Weighted average of individual GoETF Scores (base)
    - Pairwise holdings overlap penalty (up to −2 pts for 100% overlap)
    - Geographic diversification bonus (up to +1 pt)

    Request body: {"portfolio": [{"etf_id": "SWDA", "weight": 60}, ...]}
    """
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]

    return compute_portfolio_score(db, resolved_portfolio, rf_annual=rf_rate)
