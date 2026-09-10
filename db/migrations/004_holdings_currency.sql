-- Nullable: historical holdings must not inherit the ETF's base currency.
ALTER TABLE holdings ADD COLUMN IF NOT EXISTS currency VARCHAR(3);