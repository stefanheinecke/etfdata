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


def _is_demo(api_key: APIKey) -> bool:
    return getattr(api_key, "name", "") == "__demo__"


@router.get("/etfs")
async def get_etf_scores(
    tickers: Optional[str] = None,
    rf_rate: float = 0.04,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
):
    """
    GoETF Score for all ETFs (or a comma-separated ticker subset).
    Each ETF receives a 1–10 composite score based on 8 risk/diversification metrics.
    """
    etf_ids = None

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if _is_demo(api_key):
            if any(t != "SWDA" for t in ticker_list):
                raise HTTPException(
                    status_code=403,
                    detail="Demo key only allows access to the SWDA ETF.",
                )
        resolved = [resolve_etf(db, t) for t in ticker_list]
        etf_ids = [e.id for e in resolved]
    elif _is_demo(api_key):
        swda = db.query(ETF).filter(ETF.ticker == "SWDA").first()
        etf_ids = [swda.id] if swda else []

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
    - A swap tip: the single-ETF replacement that most improves the score.

    Request body: {"portfolio": [{"etf_id": "SWDA", "weight": 60}, ...]}
    """
    resolved_portfolio = [
        {"etf_id": str(resolve_etf(db, item["etf_id"]).id), "weight": item["weight"]}
        for item in request.portfolio
    ]

    return compute_portfolio_score(db, resolved_portfolio, rf_annual=rf_rate)
