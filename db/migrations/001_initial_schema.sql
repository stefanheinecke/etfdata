-- ETF Analytics Database Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ETF Master Data
CREATE TABLE etfs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    isin VARCHAR(12) UNIQUE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    domicile VARCHAR(2) NOT NULL,
    replication_method VARCHAR(50),
    ter DECIMAL(5, 3),
    fund_size BIGINT,
    benchmark VARCHAR(255),
    currency VARCHAR(3) NOT NULL,
    listings JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_etfs_ticker ON etfs(ticker);
CREATE INDEX idx_etfs_provider ON etfs(provider);

-- Holdings
CREATE TABLE holdings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    etf_id UUID NOT NULL REFERENCES etfs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    instrument_isin VARCHAR(12) NOT NULL,
    instrument_name VARCHAR(255) NOT NULL,
    weight DECIMAL(8, 4) NOT NULL,
    country VARCHAR(2),
    sector VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_holdings_etf_date ON holdings(etf_id, date);
CREATE INDEX idx_holdings_country ON holdings(country);
CREATE INDEX idx_holdings_sector ON holdings(sector);
CREATE UNIQUE INDEX idx_holdings_unique ON holdings(etf_id, date, instrument_isin);

-- Allocations (Sector, Country, Currency)
CREATE TABLE allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    etf_id UUID NOT NULL REFERENCES etfs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    type VARCHAR(20) NOT NULL,
    bucket VARCHAR(100) NOT NULL,
    weight DECIMAL(8, 4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_allocations_etf_type_date ON allocations(etf_id, type, date);
CREATE UNIQUE INDEX idx_allocations_unique ON allocations(etf_id, date, type, bucket);

-- Performance Data (Optional MVP)
CREATE TABLE performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    etf_id UUID NOT NULL REFERENCES etfs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    nav DECIMAL(12, 4),
    close_price DECIMAL(12, 4),
    currency VARCHAR(3) NOT NULL,
    dividend DECIMAL(12, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_performance_etf_date ON performance(etf_id, date);
CREATE UNIQUE INDEX idx_performance_unique ON performance(etf_id, date);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    rate_limit_per_minute INT DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_api_keys_key ON api_keys(key);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);

-- ETL Jobs Tracking
CREATE TABLE etl_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(100) NOT NULL,
    status VARCHAR(20),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    records_processed INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_etl_jobs_name_status ON etl_jobs(job_name, status);
