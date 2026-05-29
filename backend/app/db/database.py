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
    Base.metadata.create_all(bind=engine)
    # Additive column migrations (idempotent via IF NOT EXISTS)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
        conn.commit()
