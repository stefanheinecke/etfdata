from sqlalchemy.orm import Session


def seed_database(db: Session) -> dict:
    """No-op — dummy ETF data has been removed. Use /admin/import-ishares to import real data."""
    return {"etfs": 0, "holdings": 0, "allocations": 0, "performance": 0}
