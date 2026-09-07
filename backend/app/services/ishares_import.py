"""
Shared iShares/yfinance helpers: country-code lookup (used by etf_import_service)
and the daily price refresh job.

The hardcoded 13-ETF holdings/sector-weights catalogue and its yfinance-based
bulk importer were removed — ETF metadata now comes from provider Excel exports
(see import_provider_metadata.py) and holdings from factsheet/PDF extraction.
"""

import logging
import time

import yfinance as yf
from sqlalchemy.orm import Session

from app.schemas import ETF

logger = logging.getLogger(__name__)

# Cache country lookups across ETFs so AAPL / MSFT etc. are only fetched once
_country_cache: dict[str, str] = {}

# yfinance returns full country names; map to ISO-3166-1 alpha-2 codes (VARCHAR(2) in DB)
_COUNTRY_ISO: dict[str, str] = {
    "Argentina": "AR", "Australia": "AU", "Austria": "AT", "Bahrain": "BH",
    "Belgium": "BE", "Bermuda": "BM", "Brazil": "BR",
    "Bulgaria": "BG", "Canada": "CA", "Cayman Islands": "KY", "Chile": "CL",
    "China": "CN", "Colombia": "CO", "Croatia": "HR", "Cyprus": "CY",
    "Czech Republic": "CZ", "Czechia": "CZ",
    "Denmark": "DK", "Egypt": "EG", "Finland": "FI", "France": "FR",
    "Germany": "DE", "Greece": "GR", "Hong Kong": "HK", "Hungary": "HU",
    "India": "IN", "Indonesia": "ID", "Ireland": "IE", "Israel": "IL",
    "Italy": "IT", "Japan": "JP", "Jordan": "JO", "Kazakhstan": "KZ",
    "Kenya": "KE", "Korea": "KR", "South Korea": "KR",
    "Kuwait": "KW", "Luxembourg": "LU", "Malaysia": "MY", "Mexico": "MX",
    "Morocco": "MA", "Netherlands": "NL", "New Zealand": "NZ", "Nigeria": "NG",
    "Norway": "NO", "Pakistan": "PK", "Peru": "PE", "Philippines": "PH",
    "Poland": "PL", "Portugal": "PT", "Qatar": "QA", "Romania": "RO",
    "Russia": "RU", "Saudi Arabia": "SA", "Serbia": "RS",
    "Singapore": "SG", "Slovenia": "SI", "South Africa": "ZA", "Spain": "ES",
    "Sri Lanka": "LK", "Sweden": "SE", "Switzerland": "CH",
    "Taiwan": "TW", "Thailand": "TH", "Turkey": "TR",
    "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States": "US", "USA": "US", "Uruguay": "UY", "Vietnam": "VN",
}


def _lookup_country(symbol: str) -> str:
    """Return the ISO-2 country code for a ticker symbol, cached to minimise API calls."""
    if symbol in _country_cache:
        return _country_cache[symbol]
    try:
        full_name = yf.Ticker(symbol).info.get("country", "") or ""
        code = _COUNTRY_ISO.get(full_name, "")
        time.sleep(0.4)  # light delay between lookups
    except Exception:
        code = ""
    _country_cache[symbol] = code
    return code


def _eodhd_symbol_for_etf(etf) -> str | None:
    """
    Return the EODHD-format price symbol for an ETF.
    Returns etf.listings["eodhd_symbol"] if stored, otherwise None.
    (Ticker-based lookup removed since ticker column no longer exists)
    """
    if etf.listings and etf.listings.get("eodhd_symbol"):
        return etf.listings["eodhd_symbol"]
    return None


def refresh_daily_prices(db: Session, progress_cb=None) -> dict:
    """
    Fetch the latest 7 calendar days of closing prices for every ETF in the
    database and upsert into the performance table.  Existing rows are updated
    in-place; no data is deleted.  Designed to be called once per trading day.

    Requires EODHD_TOKEN and etf.listings['eodhd_symbol'] to be set (see
    /admin/backfill-eodhd-symbols). ETFs without a resolvable EODHD symbol
    are skipped and reported in the `errors` list.

    progress_cb: optional callable(done, total, ticker) called before each ETF.
    """
    import os
    from datetime import datetime, timedelta
    from app.services.etf_import_service import upsert_eodhd_prices

    token = os.getenv("EODHD_TOKEN")
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    etfs = db.query(ETF).order_by(ETF.isin).all()
    total = len(etfs)
    total_rows = 0
    etf_results = []
    errors = []

    for i, etf in enumerate(etfs):
        if progress_cb:
            progress_cb(i, total, etf.isin)

        eodhd_sym = _eodhd_symbol_for_etf(etf)
        if not token or not eodhd_sym:
            errors.append(f"{etf.isin}: no EODHD_TOKEN or eodhd_symbol configured")
            continue

        try:
            actual_currency = etf.currency or "USD"
            count = upsert_eodhd_prices(
                etf_id=etf.id,
                eodhd_symbol=eodhd_sym,
                token=token,
                db=db,
                from_date=from_date,
                currency=actual_currency,
            )

            db.commit()
            total_rows += count
            etf_results.append({"isin": etf.isin, "rows_upserted": count, "source": "eodhd"})
            logger.info("refresh_daily_prices: %s — %d rows via eodhd", etf.isin, count)

        except Exception as exc:
            db.rollback()
            errors.append(f"{etf.isin}: {exc}")
            logger.error("refresh_daily_prices failed for %s: %s", etf.isin, exc)

    if progress_cb:
        progress_cb(total, total, "")

    return {
        "total_rows_upserted": total_rows,
        "total_etfs": total,
        "etfs": etf_results,
        "errors": errors,
    }
