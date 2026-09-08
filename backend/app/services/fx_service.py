"""
fx_service.py — daily FX rates (via Frankfurter, https://frankfurter.dev — free,
no API key, no quotas, sourced from 84 central banks) for cross-currency fund
size comparison. Stores one row per (date, source_currency, target_currency)
in the fx_rates table; the latest stored rate is used to convert fund_size
into a common display currency (USD).
"""
from datetime import date
from typing import Optional

import requests as _req
from sqlalchemy.orm import Session

from app.schemas import ETF, FXRate

_FRANKFURTER_BASE = "https://api.frankfurter.dev/v2"
DISPLAY_CURRENCY = "USD"


def fetch_latest_rates(target_currency: str = DISPLAY_CURRENCY) -> tuple:
    """Fetch the latest target_currency-based rates for every currency in one call.
    Returns (as_of_date, {currency: units_of_currency_per_1_target_currency}).
    Raises RuntimeError with the response detail on failure."""
    resp = _req.get(f"{_FRANKFURTER_BASE}/rates", params={"base": target_currency}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Frankfurter HTTP {resp.status_code}: {resp.text[:200]}")
    # v2 returns a flat list: [{"date": "...", "base": "USD", "quote": "AED", "rate": 3.67}, ...]
    data = resp.json()
    if not data:
        raise RuntimeError(f"Frankfurter returned no rates: {data}")
    rates = {row["quote"]: row["rate"] for row in data if row.get("quote") and row.get("rate")}
    as_of = data[0].get("date")
    if not rates or not as_of:
        raise RuntimeError(f"Frankfurter returned no usable rates: {data[:3]}")
    return date.fromisoformat(as_of), rates


def _store_rate(db: Session, as_of: date, source_currency: str, target_currency: str, rate: float) -> None:
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


def refresh_all_fx_rates(db: Session, target_currency: str = DISPLAY_CURRENCY) -> dict:
    """Fetch the latest rates (one API call) and store source_currency->target_currency
    (inverted from Frankfurter's target_currency-based rates) for every distinct ETF currency."""
    currencies = sorted({
        (c or "").strip().upper()[:3]
        for (c,) in db.query(ETF.currency).filter(ETF.currency.isnot(None)).distinct().all()
        if c
    })
    if not currencies:
        return {"results": []}

    try:
        as_of, rates_from_target = fetch_latest_rates(target_currency)
    except Exception as exc:
        return {"error": str(exc), "results": []}

    results = []
    for cur in currencies:
        if cur == target_currency:
            rate = 1.0
        else:
            target_to_cur = rates_from_target.get(cur)
            if not target_to_cur:
                results.append({"source_currency": cur, "target_currency": target_currency,
                                 "status": "error", "error": f"No rate for '{cur}' in Frankfurter response"})
                continue
            rate = 1.0 / target_to_cur
        _store_rate(db, as_of, cur, target_currency, rate)
        results.append({"source_currency": cur, "target_currency": target_currency,
                         "date": as_of.isoformat(), "rate": rate, "status": "ok"})
    db.commit()
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
