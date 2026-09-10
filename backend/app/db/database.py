import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/etfdata")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.schemas import Base
    from sqlalchemy import text
    with engine.connect() as conn:
        # Drop pending_key_requests if it was created with the wrong schema
        # (a deployment bug merged ETLJob columns into it — safe to drop, it's ephemeral data)
        conn.execute(text("""
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'pending_key_requests' AND column_name = 'job_name'
                ) THEN
                    DROP TABLE pending_key_requests;
                END IF;
            END $$;
        """))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    # Additive column migrations (idempotent via IF NOT EXISTS)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS dividend_policy VARCHAR(20)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS replication_method VARCHAR(50)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS asset_class VARCHAR(50)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS sfdr_classification VARCHAR(10)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS inception_date DATE"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS wkn VARCHAR(20)"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS num_constituents INTEGER"))
        conn.execute(text("ALTER TABLE etfs ADD COLUMN IF NOT EXISTS data_source VARCHAR(50)"))
        # fund_size was originally created as INTEGER; widen to BIGINT to match the model
        # (large-AUM funds in JPY/other low-denomination currencies overflow 32-bit int)
        conn.execute(text("ALTER TABLE etfs ALTER COLUMN fund_size TYPE BIGINT"))
        conn.execute(text("ALTER TABLE etfs ALTER COLUMN isin SET NOT NULL"))
        conn.execute(text("ALTER TABLE etfs ALTER COLUMN provider DROP NOT NULL"))
        conn.execute(text("ALTER TABLE etfs ALTER COLUMN domicile DROP NOT NULL"))
        conn.execute(text("ALTER TABLE etfs ALTER COLUMN currency DROP NOT NULL"))
        conn.execute(text("ALTER TABLE performance ALTER COLUMN currency DROP NOT NULL"))
        conn.execute(text("ALTER TABLE holdings ALTER COLUMN instrument_isin TYPE VARCHAR(50)"))
        conn.execute(text("ALTER TABLE holdings ADD COLUMN IF NOT EXISTS currency VARCHAR(3)"))
        # Drop ticker column — ISIN is now the primary identifier
        conn.execute(text("ALTER TABLE etfs DROP COLUMN IF EXISTS ticker"))
        # Update holdings schema: make instrument_isin nullable and update unique constraint
        # Use DO block to handle migrations safely
        conn.execute(text("""
            DO $$ BEGIN
                -- Make instrument_isin nullable if it exists
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='holdings' AND column_name='instrument_isin'
                ) THEN
                    ALTER TABLE holdings ALTER COLUMN instrument_isin DROP NOT NULL;
                END IF;
            END $$;
        """))
        
        from pathlib import Path
        migration = Path(__file__).with_name("holdings_isin_unique.sql").read_text(encoding="utf-8")
        conn.execute(text(migration))
        
        # Add index on instrument_isin for optional lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_holdings_isin ON holdings (instrument_isin)
        """))
        
        # Ensure holdings.id is auto-generated at the DB level (not just via the ORM default)
        conn.execute(text("ALTER TABLE holdings ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
        
        # Create settings table if it doesn't exist and initialize default contact email
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Insert default contact email if not already set
        conn.execute(text("""
            INSERT INTO settings (id, key, value) 
            VALUES (gen_random_uuid(), 'contact_email', 'stefan.heinecke1@gmail.com')
            ON CONFLICT (key) DO NOTHING
        """))
        
        # Create contact_messages table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_contact_messages_email ON contact_messages (email)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON contact_messages (created_at)
        """))
        
        conn.commit()
