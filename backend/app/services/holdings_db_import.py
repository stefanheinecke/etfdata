"""Persist an already-retrieved provider basket. No network/provider logic here."""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.asset_classes import normalize_bucket


def prepare_holdings(etf_isin: str, holdings: list[dict]) -> tuple[date, list[dict]]:
    """Convert script fractions to DB percentages before changing any records."""
    if not holdings:
        raise ValueError("Cannot import an empty holdings basket")
    dates = set()
    records = {}
    classifications = {}
    for index, holding in enumerate(holdings):
        if holding.get("etf_isin") != etf_isin:
            raise ValueError("Holding belongs to a different ETF")
        if holding.get("estimate_type") != "provider_reported_equity_basket":
            raise ValueError("Only provider-reported holdings may be imported, not demo/reconstructed baskets")
        as_of = date.fromisoformat(holding["as_of"])
        if as_of > datetime.now(timezone.utc).date():
            raise ValueError("Holdings date cannot be in the future")
        dates.add(as_of)
        name = str(holding.get("name") or "").strip()
        if not name or len(name) > 255:
            raise ValueError("Holding name must contain 1–255 characters")
        isin = holding.get("isin")
        if isinstance(isin, str):
            isin = isin.strip().upper() or None
        if isin is not None and (not isinstance(isin, str) or len(isin) != 12):
            raise ValueError("Invalid constituent ISIN; use the provider's ISIN validation first")
        raw_weight = holding.get("reported_weight")
        if raw_weight is None or isinstance(raw_weight, bool):
            raise ValueError("Missing published NAV weight")
        weight = Decimal(str(raw_weight)) * 100
        if not weight.is_finite() or not 0 <= weight <= 105:
            raise ValueError("Published NAV weight must be finite and between 0% and 105%")
        # Unknown ISINs cannot safely identify the same security, even by name.
        key = ("isin", isin) if isin else ("unresolved", index)
        if key in records:
            records[key]["weight"] += weight
        else:
            records[key] = {"instrument_isin": isin, "instrument_name": name, "weight": weight}
            classifications[key] = {"country": set(), "sector": set(), "currency": set()}
        for field, values in classifications[key].items():
            value = normalize_bucket(holding.get(field), field)
            if value is not None:
                values.add(value)
    if len(dates) != 1:
        raise ValueError("All imported holdings must have the same valuation date")
    total = sum(row["weight"] for row in records.values())
    if not 0 < total <= 105:
        raise ValueError("Total published equity weight must be greater than 0% and at most 105%")
    # Missing labels provide no evidence. Conflicts stay unknown regardless of row order.
    for key, row in records.items():
        for field, values in classifications[key].items():
            row[field] = next(iter(values)) if len(values) == 1 else None
    return dates.pop(), list(records.values())


def import_holdings(db, etf_isin: str, holdings: list[dict]) -> dict:
    """Replace holdings for one ETF/date; caller owns commit and rollback.

    ETF metadata must already exist. Other dates, ETF metadata, prices and
    allocations are untouched. Additional providers can reuse the same format.
    """
    as_of, records = prepare_holdings(etf_isin, holdings)
    from app.schemas import ETF, Holding

    etf = db.query(ETF).filter_by(isin=etf_isin).with_for_update().first()
    if etf is None:
        raise ValueError(f"ETF {etf_isin} not found; import its metadata first")
    deleted = db.query(Holding).filter_by(etf_id=etf.id, date=as_of).delete(synchronize_session=False)
    db.add_all([Holding(etf_id=etf.id, date=as_of, **row) for row in records])
    db.flush()
    return {"isin": etf_isin, "as_of": as_of.isoformat(), "imported": len(records), "replaced": deleted}


def import_to_database(etf_isin: str, holdings: list[dict]) -> dict:
    """Use the project's SQLAlchemy/PostgreSQL configuration and one transaction."""
    import os

    if not os.environ.get("DATABASE_URL"):
        raise ValueError("Set DATABASE_URL to the target PostgreSQL database before using --import-db")
    try:
        from app.db.database import SessionLocal
        from sqlalchemy.exc import SQLAlchemyError
    except ImportError as exc:
        raise RuntimeError("Database import requires the backend dependencies (SQLAlchemy and psycopg2)") from exc

    try:
        with SessionLocal() as db:
            with db.begin():
                result = import_holdings(db, etf_isin, holdings)
        return result
    except SQLAlchemyError as exc:
        # SQLAlchemy errors can contain connection details or full SQL parameters.
        raise RuntimeError("Database import failed; transaction rolled back. Check database connectivity and schema.") from exc