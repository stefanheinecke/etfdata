from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import APIKey
from app.api.utils import resolve_etf
from app.services.scoring_service import compute_goetf_scores

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/etfs")
async def get_etf_scores(
    isins: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
):
    """
    GoETF Score for all ETFs (or a comma-separated ISIN subset).
    Each ETF receives a 1-10 quality score based on six equally weighted
    holdings-concentration, diversification, and fund-size components.
    """
    etf_ids = None

    if isins:
        isin_list = [t.strip().upper() for t in isins.split(",") if t.strip()]
        resolved = [resolve_etf(db, t) for t in isin_list]
        etf_ids = [e.id for e in resolved]

    return compute_goetf_scores(db, etf_ids=etf_ids)
