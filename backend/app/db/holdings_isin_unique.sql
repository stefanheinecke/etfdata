DO $$
BEGIN
    LOCK TABLE holdings IN ACCESS EXCLUSIVE MODE;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'holdings'::regclass AND conname = 'idx_holdings_unique_isin'
    ) THEN
        ALTER TABLE holdings DROP CONSTRAINT IF EXISTS idx_holdings_unique;
        DROP INDEX IF EXISTS idx_holdings_unique;

        UPDATE holdings
        SET instrument_isin = NULLIF(UPPER(BTRIM(instrument_isin)), '');

        -- Preserve total exposure while retaining the most recent row's descriptive fields.
        WITH ranked AS (
            SELECT id,
                   SUM(weight) OVER (PARTITION BY etf_id, date, instrument_isin) AS total_weight,
                   ROW_NUMBER() OVER (
                       PARTITION BY etf_id, date, instrument_isin
                       ORDER BY created_at DESC NULLS LAST, id
                   ) AS position
            FROM holdings
            WHERE instrument_isin IS NOT NULL
        )
        UPDATE holdings h SET weight = r.total_weight
        FROM ranked r WHERE h.id = r.id AND r.position = 1;

        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY etf_id, date, instrument_isin
                ORDER BY created_at DESC NULLS LAST, id
            ) AS position
            FROM holdings
            WHERE instrument_isin IS NOT NULL
        )
        DELETE FROM holdings h USING ranked r
        WHERE h.id = r.id AND r.position > 1;

        ALTER TABLE holdings ADD CONSTRAINT idx_holdings_unique_isin
            UNIQUE (etf_id, date, instrument_isin);
    END IF;
END $$;