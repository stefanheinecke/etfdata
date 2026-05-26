-- Add exchange column to holdings to distinguish cross-listed securities (e.g. TRU on NYSE vs JSE)
-- exchange is NOT NULL DEFAULT '' so the unique constraint works correctly (NULLs are not equal in PostgreSQL)

ALTER TABLE holdings ADD COLUMN exchange VARCHAR(20) NOT NULL DEFAULT '';

DROP INDEX idx_holdings_unique;
CREATE UNIQUE INDEX idx_holdings_unique ON holdings(etf_id, date, instrument_isin, exchange);
