from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel

class ETFBase(BaseModel):
    isin: Optional[str] = None
    ticker: str
    name: str
    provider: Optional[str] = None
    domicile: Optional[str] = None
    ter: Optional[Decimal] = None
    fund_size: Optional[int] = None
    benchmark: Optional[str] = None
    currency: Optional[str] = None
    dividend_policy: Optional[str] = None
    listings: Optional[dict] = None

class ETFCreate(ETFBase):
    pass

class ETFResponse(ETFBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class HoldingBase(BaseModel):
    date: date
    instrument_isin: str
    instrument_name: str
    weight: Decimal
    country: Optional[str] = None
    sector: Optional[str] = None

class HoldingCreate(HoldingBase):
    etf_id: UUID

class HoldingResponse(HoldingBase):
    id: UUID
    etf_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class AllocationBase(BaseModel):
    date: date
    type: str
    bucket: str
    weight: Decimal

class AllocationCreate(AllocationBase):
    etf_id: UUID

class AllocationResponse(AllocationBase):
    id: UUID
    etf_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class PerformanceBase(BaseModel):
    date: date
    nav: Optional[Decimal] = None
    close_price: Optional[Decimal] = None
    currency: Optional[str] = None
    dividend: Optional[Decimal] = None

class PerformanceCreate(PerformanceBase):
    etf_id: UUID

class PerformanceResponse(PerformanceBase):
    id: UUID
    etf_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class OverlapRequest(BaseModel):
    etf_ids: List[str]
    date: Optional[date] = None

class OverlapResponse(BaseModel):
    matrix: dict
    common_holdings: List[dict]

class ExposureRequest(BaseModel):
    portfolio: List[dict]

class ExposureResponse(BaseModel):
    sectors: dict
    countries: dict
    currencies: dict

class SimilarityResponse(BaseModel):
    similar_etfs: List[dict]

class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
