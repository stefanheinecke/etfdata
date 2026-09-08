"""
fx_service.py — daily FX rates (via EODHD forex API) for cross-currency fund
size comparison. Stores one row per (date, source_currency, target_currency)
in the fx_rates table; the latest stored rate is used to convert fund_size
into a common display currency (USD).
"""
import os
from datetime import date, timedelta
from typing import Optional

import requests as _req
from sqlalchemy.orm import Session

from app.schemas import ETF, FXRate

_EODHD_BASE = "https://eodhd.com/api"
DISPLAY_CURRENCY = "USD"


def fetch_latest_rate(source_currency: str, target_currency: str, token: str) -> Optional[tuple]:
    """Fetch the most recent EODHD forex close for source_currency->target_currency.
    Returns (date, rate) or None if unavailable."""
    if source_currency == target_currency:
        return date.today(), 1.0

    symbol = f"{source_currency}{target_currency}.FOREX"
    resp = _req.get(
        f"{_EODHD_BASE}/eod/{symbol}",
        params={
            "api_token": token, "fmt": "json",
            "from": (date.today() - timedelta(days=10)).isoformat(),
            "to": date.today().isoformat(), "period": "d",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    if not rows:
        return None
    latest = max(rows, key=lambda r: r["date"])
    close = latest.get("adjusted_close") or latest.get("close")
    if not close:
        return None
    return date.fromisoformat(latest["date"]), float(close)


def upsert_fx_rate(db: Session, source_currency: str, target_currency: str, token: str) -> dict:
    result = fetch_latest_rate(source_currency, target_currency, token)
    if not result:
        return {"source_currency": source_currency, "target_currency": target_currency,
                "status": "error", "error": "No FX data returned"}

    as_of, rate = result
    existing = (
        db.query(FXRate)
        .filter_by(date=as_of, source_currency=source_currency, target_currency=target_currency)
        .first()
    )
    if existing:
        existing.rate = rate
    else:
        db.add(FXRate(date=as_of, source_currency=source_currency,
                       target_currency=target_currency, rate=rate))
    db.commit()
    return {"source_currency": source_currency, "target_currency": target_currency,
            "date": as_of.isoformat(), "rate": rate, "status": "ok"}


def refresh_all_fx_rates(db: Session, target_currency: str = DISPLAY_CURRENCY) -> dict:
    """Fetch/store the latest rate to `target_currency` for every distinct ETF currency."""
    token = os.getenv("EODHD_TOKEN")
    if not token:
        return {"error": "EODHD_TOKEN not set", "results": []}

    currencies = sorted({
        (c or "").strip().upper()[:3]
        for (c,) in db.query(ETF.currency).filter(ETF.currency.isnot(None)).distinct().all()
        if c
    })
    results = [upsert_fx_rate(db, cur, target_currency, token) for cur in currencies]
    return {"results": results}


def get_latest_rate(db: Session, source_currency: Optional[str], target_currency: str = DISPLAY_CURRENCY) -> Optional[float]:
    """Latest stored rate for source_currency -> target_currency, or 1.0 if they match."""
    if not source_currency:
        return None
    source_currency = source_currency.strip().upper()[:3]
    if source_currency == target_currency:
        return 1.0
    row = (
        db.query(FXRate)
        .filter_by(source_currency=source_currency, target_currency=target_currency)
        .order_by(FXRate.date.desc())
        .first()
    )
    return float(row.rate) if row else None


def get_latest_rates_map(db: Session, source_currencies: set, target_currency: str = DISPLAY_CURRENCY) -> dict:
    """Batch version of get_latest_rate — one query per currency (small distinct set), avoids N+1 per ETF row."""
    normalized = {(c or "").strip().upper()[:3] for c in source_currencies if c}
    return {cur: get_latest_rate(db, cur, target_currency) for cur in normalized}
