from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Numeric, Date, Boolean, Text, JSON, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class ETF(Base):
    __tablename__ = "etfs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    isin = Column(String(12), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=True, index=True)
    domicile = Column(String(2), nullable=True)
    ter = Column(Numeric(5, 3))
    fund_size = Column(BigInteger)
    benchmark = Column(String(255))
    currency = Column(String(3), nullable=True)
    dividend_policy = Column(String(20))  # "Accumulating" | "Distributing"
    replication_method = Column(String(50))  # "Physical (Full replication)" | "Physical (Sampling)" | "Synthetic"
    asset_class = Column(String(50))  # "Equities" | "Bonds" | "Real Estate" | "Commodities" | "Precious Metals" | ...
    sfdr_classification = Column(String(10))  # "Art.6" | "Art.8" | "Art.9"
    inception_date = Column(Date)
    wkn = Column(String(20))
    num_constituents = Column(Integer)
    data_source = Column(String(50))  # provenance of the metadata, e.g. "UBS", "iShares", "EODHD", "PDF"
    listings = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    holdings = relationship("Holding", back_populates="etf", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="etf", cascade="all, delete-orphan")
    performance = relationship("Performance", back_populates="etf", cascade="all, delete-orphan")

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    etf_id = Column(PGUUID(as_uuid=True), ForeignKey("etfs.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    instrument_isin = Column(String(50), nullable=True)  # May not be available in all factsheets
    instrument_name = Column(String(255), nullable=False)
    weight = Column(Numeric(8, 4), nullable=False)
    country = Column(String(2), index=True)
    sector = Column(String(100), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    etf = relationship("ETF", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint("etf_id", "date", "instrument_name", name="idx_holdings_unique"),
        Index("idx_holdings_etf_date", "etf_id", "date"),
        Index("idx_holdings_isin", "instrument_isin"),  # For optional ISIN lookups
    )

class Allocation(Base):
    __tablename__ = "allocations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    etf_id = Column(PGUUID(as_uuid=True), ForeignKey("etfs.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    type = Column(String(20), nullable=False)
    bucket = Column(String(100), nullable=False)
    weight = Column(Numeric(8, 4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    etf = relationship("ETF", back_populates="allocations")

    __table_args__ = (
        UniqueConstraint("etf_id", "date", "type", "bucket", name="idx_allocations_unique"),
        Index("idx_allocations_etf_type_date", "etf_id", "type", "date"),
    )

class Performance(Base):
    __tablename__ = "performance"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    etf_id = Column(PGUUID(as_uuid=True), ForeignKey("etfs.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    nav = Column(Numeric(12, 4))
    close_price = Column(Numeric(12, 4))
    currency = Column(String(3), nullable=True)
    dividend = Column(Numeric(12, 4))
    created_at = Column(DateTime, default=datetime.utcnow)

    etf = relationship("ETF", back_populates="performance")

    __table_args__ = (
        UniqueConstraint("etf_id", "date", name="idx_performance_unique"),
        Index("idx_performance_etf_date", "etf_id", "date"),
    )

class FXRate(Base):
    __tablename__ = "fx_rates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    date = Column(Date, nullable=False)
    source_currency = Column(String(3), nullable=False)
    target_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "source_currency", "target_currency", name="idx_fx_rates_unique"),
        Index("idx_fx_rates_pair_date", "source_currency", "target_currency", "date"),
    )

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    rate_limit_per_minute = Column(Integer, default=60)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)

class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    api_key_name = Column(String(100))
    email = Column(String(255))
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    query_string = Column(Text)
    request_body = Column(Text)
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    client_ip = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_request_logs_created_at", "created_at"),
        Index("idx_request_logs_api_key_id", "api_key_id"),
    )

class PendingKeyRequest(Base):
    __tablename__ = "pending_key_requests"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    is_replacement = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class ETLJob(Base):
    __tablename__ = "etl_jobs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_name = Column(String(100), nullable=False)
    status = Column(String(20))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    records_processed = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
