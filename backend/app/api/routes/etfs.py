from uuid import UUID
from datetime import date as date_type
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.core.auth import verify_api_key
from app.schemas import ETF, APIKey
from app.models import ETFCreate, ETFResponse

router = APIRouter(prefix="/etfs", tags=["etfs"])

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
    return query.offset(skip).limit(limit).all()

@router.get("/{etf_id}", response_model=ETFResponse)
async def get_etf(
    etf_id: UUID,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")
    return etf

@router.get("/{etf_id}/holdings")
async def get_holdings(
    etf_id: UUID,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Holding

    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    query = db.query(Holding).filter(Holding.etf_id == etf_id)

    if date:
        query = query.filter(Holding.date == date)
    else:
        latest_date = db.query(func.max(Holding.date)).filter(
            Holding.etf_id == etf_id
        ).scalar()
        if latest_date:
            query = query.filter(Holding.date == latest_date)

    holdings = query.all()
    return [h for h in holdings]

@router.get("/{etf_id}/allocations")
async def get_allocations(
    etf_id: UUID,
    type: Optional[str] = None,
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Allocation

    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    query = db.query(Allocation).filter(Allocation.etf_id == etf_id)

    if type:
        query = query.filter(Allocation.type == type)

    if date:
        query = query.filter(Allocation.date == date)
    else:
        latest_date = db.query(func.max(Allocation.date)).filter(
            Allocation.etf_id == etf_id
        ).scalar()
        if latest_date:
            query = query.filter(Allocation.date == latest_date)

    allocations = query.all()
    return [a for a in allocations]

@router.get("/{etf_id}/performance")
async def get_performance(
    etf_id: UUID,
    from_date: Optional[date_type] = None,
    to_date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    from app.schemas import Performance

    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    query = db.query(Performance).filter(Performance.etf_id == etf_id)

    if from_date:
        query = query.filter(Performance.date >= from_date)
    if to_date:
        query = query.filter(Performance.date <= to_date)

    performance = query.order_by(Performance.date).all()
    return [p for p in performance]

@router.delete("/{etf_id}", status_code=204)
async def delete_etf(
    etf_id: UUID,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")
    db.delete(etf)
    db.commit()

@router.delete("", status_code=200)
async def delete_etfs(
    etf_ids: List[UUID],
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key)
):
    """Delete multiple ETFs by ID list. Returns count of deleted records."""
    deleted = 0
    for etf_id in etf_ids:
        etf = db.query(ETF).filter(ETF.id == etf_id).first()
        if etf:
            db.delete(etf)
            deleted += 1
    db.commit()
    return {"deleted": deleted}
