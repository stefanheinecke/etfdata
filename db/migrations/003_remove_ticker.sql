-- Remove ticker column - ISIN is now the primary ETF identifier
-- This completes the refactoring to use ISIN instead of ticker

ALTER TABLE etfs DROP COLUMN ticker;
