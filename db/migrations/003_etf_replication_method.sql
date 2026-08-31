-- Add replication_method column to etfs table
ALTER TABLE etfs ADD COLUMN IF NOT EXISTS replication_method VARCHAR(50);
