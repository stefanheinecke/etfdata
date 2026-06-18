"""
ETF holdings importer — uses yfinance as data source.

iShares direct CSV downloads are protected by bot-detection; yfinance
provides top-10 holdings and full sector weightings for all 13 ETFs via
the Yahoo Finance funds API, which is publicly accessible.
"""

import logging
import time
from datetime import date
from typing import Optional
from uuid import uuid4

import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.schemas import ETF, Holding, Allocation, Performance

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


# Sector key normalisation (yfinance uses camelCase / snake_case keys)
_SECTOR_NAMES: dict[str, str] = {
    "realestate": "Real Estate",
    "consumer_cyclical": "Consumer Discretionary",
    "basic_materials": "Basic Materials",
    "consumer_defensive": "Consumer Staples",
    "technology": "Technology",
    "communication_services": "Communication Services",
    "financial_services": "Financials",
    "utilities": "Utilities",
    "industrials": "Industrials",
    "energy": "Energy",
    "healthcare": "Healthcare",
    "government": "Government",
    "corporate": "Corporate",
    "securitized": "Securitized",
    "municipal": "Municipal",
    "cash_equivalents": "Cash & Equivalents",
}

# ETF catalogue
# yf_symbol: ticker used to look up data on Yahoo Finance.
# For European ETFs the exchange suffix is required (SWDA.L, CSSPX.SW, etc.).
ISHARES_ETFS: list[dict] = [
    # US-listed ETFs
    # Download URL pattern: https://www.ishares.com/us/products/{id}/{TICKER}/1467271812596.ajax?tab=all&fileType=csv
    {"yf_symbol": "IVV", "ticker": "IVV", "name": "iShares Core S&P 500 ETF", "isin": "US4642872000", "currency": "USD", "domicile": "US", "ter": 0.03, "benchmark": "S&P 500 Index",
     "holdings_url": "https://www.ishares.com/us/products/239726/ISHARES_CORE_SP_500_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IWM", "ticker": "IWM", "name": "iShares Russell 2000 ETF", "isin": "US4642876555", "currency": "USD", "domicile": "US", "ter": 0.19, "benchmark": "Russell 2000 Index",
     "holdings_url": "https://www.ishares.com/us/products/239710/ISHARES_RUSSELL_2000_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IWF", "ticker": "IWF", "name": "iShares Russell 1000 Growth ETF", "isin": "US4642876308", "currency": "USD", "domicile": "US", "ter": 0.19, "benchmark": "Russell 1000 Growth Index",
     "holdings_url": "https://www.ishares.com/us/products/239706/ISHARES_RUSSELL_1000_GROWTH_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IWD", "ticker": "IWD", "name": "iShares Russell 1000 Value ETF", "isin": "US4642876316", "currency": "USD", "domicile": "US", "ter": 0.19, "benchmark": "Russell 1000 Value Index",
     "holdings_url": "https://www.ishares.com/us/products/239708/ISHARES_RUSSELL_1000_VALUE_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IJH", "ticker": "IJH", "name": "iShares Core S&P Mid-Cap ETF", "isin": "US4642874329", "currency": "USD", "domicile": "US", "ter": 0.05, "benchmark": "S&P MidCap 400 Index",
     "holdings_url": "https://www.ishares.com/us/products/239763/ISHARES_CORE_SP_MIDCAP_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IJR", "ticker": "IJR", "name": "iShares Core S&P Small-Cap ETF", "isin": "US46428V7X74", "currency": "USD", "domicile": "US", "ter": 0.06, "benchmark": "S&P SmallCap 600 Index",
     "holdings_url": "https://www.ishares.com/us/products/239774/ISHARES_CORE_SP_SMALLCAP_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "EFA", "ticker": "EFA", "name": "iShares MSCI EAFE ETF", "isin": "US4642874659", "currency": "USD", "domicile": "US", "ter": 0.32, "benchmark": "MSCI EAFE Index",
     "holdings_url": "https://www.ishares.com/us/products/239623/ISHARES_MSCI_EAFE_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "EEM", "ticker": "EEM", "name": "iShares MSCI Emerging Markets ETF", "isin": "US4642864657", "currency": "USD", "domicile": "US", "ter": 0.68, "benchmark": "MSCI Emerging Markets Index",
     "holdings_url": "https://www.ishares.com/us/products/239637/ISHARES_MSCI_EMERGING_MARKETS_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "AGG", "ticker": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "isin": "US4642872422", "currency": "USD", "domicile": "US", "ter": 0.03, "benchmark": "Bloomberg U.S. Aggregate Bond Index",
     "holdings_url": "https://www.ishares.com/us/products/239458/ISHARES_CORE_TOTAL_US_BOND_MARKET_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "LQD", "ticker": "LQD", "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF", "isin": "US4642881041", "currency": "USD", "domicile": "US", "ter": 0.14, "benchmark": "Markit iBoxx USD Liquid Investment Grade Index",
     "holdings_url": "https://www.ishares.com/us/products/239566/ISHARES_IBOXX_INVESTMENT_GRADE_CORPORATE_BOND_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    # European UCITS ETFs
    # Download URL pattern: https://www.ishares.com/uk/individual/en/products/{id}/{SLUG}/1467271812596.ajax?tab=all&fileType=csv
    # perf_yf_symbol: alternate ticker for price history when the primary listing is in GBX.
    #   SWDA.L / CSNKY.L / IEDY.L trade in GBX on LSE; we use the USD-denominated
    #   Euronext Amsterdam listings so performance data is stored in USD.
    {"yf_symbol": "SWDA.L",  "perf_yf_symbol": "SWDA.SW",  "ticker": "SWDA",  "name": "iShares Core MSCI World UCITS ETF USD (Acc)",       "isin": "IE00B4L5Y983", "currency": "USD", "domicile": "IE", "ter": 0.20, "benchmark": "MSCI World Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/251882/ISHARES_CORE_MSCI_WORLD_UCITS_ETF_USD_ACC/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "CSSPX.SW", "ticker": "CSSPX", "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",             "isin": "IE00B5BMR087", "currency": "USD", "domicile": "IE", "ter": 0.07, "benchmark": "S&P 500 Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/253743/ISHARES_CORE_SP_500_UCITS_ETF_USD_ACC/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "CSNDX.SW", "ticker": "CSNDX", "name": "iShares Core NASDAQ 100 UCITS ETF USD (Acc)",          "isin": "IE00B53SZB19", "currency": "USD", "domicile": "IE", "ter": 0.33, "benchmark": "NASDAQ-100 Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/253741/ISHARES_NASDAQ_100_UCITS_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "CSNKY.L",  "perf_yf_symbol": "CSJP.AS",   "ticker": "CSNKY", "name": "iShares Core MSCI Japan IMI UCITS ETF USD (Acc)",   "isin": "IE00B52MJD48", "currency": "USD", "domicile": "IE", "ter": 0.15, "benchmark": "MSCI Japan IMI Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/264659/ISHARES_CORE_MSCI_JAPAN_IMI_UCITS_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "IEDY.L",   "perf_yf_symbol": "SEDY.AS",   "ticker": "IEDY",  "name": "iShares Emerging Markets Dividend UCITS ETF",        "isin": "IE00B652H904", "currency": "USD", "domicile": "IE", "ter": 0.65, "benchmark": "Dow Jones Emerging Markets Select Dividend Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/264139/ISHARES_EM_DIVIDEND_UCITS_ETF/1467271812596.ajax?tab=all&fileType=csv"},
    {"yf_symbol": "EIMI.L",   "perf_yf_symbol": "EIMI.SW",   "ticker": "EIMI",  "name": "iShares Core MSCI Emerging Markets IMI UCITS ETF USD (Acc)", "isin": "IE00BKM4GZ66", "currency": "USD", "domicile": "IE", "ter": 0.18, "benchmark": "MSCI Emerging Markets Investable Market Index",
     "holdings_url": "https://www.ishares.com/uk/individual/en/products/264659/ISHARES_CORE_MSCI_EMERGING_MARKETS_IMI_UCITS_ETF/1467271812596.ajax?tab=all&fileType=csv"},
]


def _upsert_etf(meta: dict, db: Session) -> ETF:
    etf = db.query(ETF).filter_by(isin=meta["isin"]).first()
    if not etf:
        etf = ETF(
            isin=meta["isin"],
            ticker=meta["ticker"],
            name=meta["name"],
            provider="iShares",
            domicile=meta["domicile"],
            ter=meta["ter"],
            currency=meta["currency"],
            benchmark=meta["benchmark"],
        )
        db.add(etf)
        db.flush()
    else:
        etf.ticker = meta["ticker"]
        etf.name = meta["name"]
        etf.ter = meta["ter"]
        etf.benchmark = meta["benchmark"]
    return etf


def _upsert_holdings(etf: ETF, holdings: list[dict], as_of: date, db: Session) -> int:
    db.query(Holding).filter_by(etf_id=etf.id, date=as_of).delete()
    for h in holdings:
        db.add(Holding(
            etf_id=etf.id,
            date=as_of,
            instrument_isin=h["isin"],
            instrument_name=h["name"],
            weight=h["weight"],
            sector=h.get("sector", "Equity"),
            country=h.get("country", ""),
        ))
    return len(holdings)


def _upsert_allocations(
    etf: ETF,
    sector_weights: dict[str, float],
    holdings_data: list[dict],
    as_of: date,
    db: Session,
) -> int:
    db.query(Allocation).filter_by(etf_id=etf.id, date=as_of).delete()
    count = 0

    # Sector allocations from yfinance funds_data
    for raw_key, weight in sector_weights.items():
        bucket = _SECTOR_NAMES.get(raw_key, raw_key.replace("_", " ").title())
        pct = round(float(weight) * 100, 4)
        if pct > 0:
            db.add(Allocation(etf_id=etf.id, date=as_of, type="sector", bucket=bucket, weight=pct))
            count += 1

    # Country allocations derived from top-10 holdings
    country_totals: dict[str, float] = {}
    for h in holdings_data:
        c = h.get("country") or ""
        if c:
            country_totals[c] = country_totals.get(c, 0.0) + float(h["weight"])
    for country, weight in country_totals.items():
        if weight > 0:
            db.add(Allocation(etf_id=etf.id, date=as_of, type="country", bucket=country, weight=round(weight, 4)))
            count += 1

    return count


def _upsert_performance(etf: ETF, ticker_obj: "yf.Ticker", db: Session,
                        perf_yf_symbol: str | None = None) -> int:
    # Use a dedicated USD-listed ticker for price history if specified
    if perf_yf_symbol:
        price_ticker = yf.Ticker(perf_yf_symbol)
        logger.info("%s: fetching price history from %s", etf.ticker, perf_yf_symbol)
    else:
        price_ticker = ticker_obj

    hist = price_ticker.history(period="max")
    if hist is None or hist.empty:
        return 0

    # Detect the actual price currency reported by yfinance
    actual_currency = etf.currency
    try:
        reported = price_ticker.fast_info.currency or ""
        if reported:
            actual_currency = reported
    except Exception:
        pass

    # GBp = pence (GBX) — divide by 100 to get GBP
    gbx_factor = 1.0
    if actual_currency in ("GBp", "GBX", "GBx"):
        gbx_factor = 0.01
        actual_currency = "GBP"
        logger.info("%s: prices are in pence (GBX), converting to GBP", etf.ticker)

    db.query(Performance).filter_by(etf_id=etf.id).delete()
    count = 0
    for idx, row in hist.iterrows():
        close = float(row["Close"]) * gbx_factor
        if close <= 0:
            continue
        db.add(Performance(
            etf_id=etf.id,
            date=idx.date(),
            close_price=round(close, 4),
            currency=actual_currency,
        ))
        count += 1
    return count


def import_ishares(db: Session, tickers: Optional[list[str]] = None) -> dict:
    """
    Fetch top holdings and sector allocations from Yahoo Finance (via yfinance)
    and upsert into the database.

    Pass tickers=None to import all ETFs, or a list of ticker symbols to import
    a subset (e.g. ["IVV", "SWDA"]).
    """
    targets = (
        ISHARES_ETFS
        if not tickers
        else [e for e in ISHARES_ETFS if e["ticker"] in tickers]
    )

    as_of = date.today()
    results = []

    for i, meta in enumerate(targets):
        if i > 0:
            time.sleep(2)  # avoid Yahoo Finance rate limiting
        result: dict = {
            "ticker": meta["ticker"],
            "status": "ok",
            "holdings": 0,
            "allocations": 0,
            "performance": 0,
            "error": None,
        }
        try:
            logger.info("Fetching yfinance data for %s (%s) ...", meta["ticker"], meta["yf_symbol"])
            # Retry up to 3 times with exponential backoff on rate-limit errors.
            # funds_data is lazy — the actual HTTP fetch happens when .top_holdings /
            # .sector_weightings are accessed, so we retry those accesses too.
            ticker_obj = yf.Ticker(meta["yf_symbol"])

            top_h = None
            sector_w: dict = {}
            for attempt in range(3):
                try:
                    funds = ticker_obj.funds_data
                    top_h = funds.top_holdings        # triggers HTTP fetch
                    sector_w = funds.sector_weightings or {}
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    if "rate" in err_str or "429" in err_str or "too many" in err_str or "failed" in err_str:
                        wait = 10 * (2 ** attempt)
                        logger.warning("Rate limited on %s, retrying in %ds …", meta["ticker"], wait)
                        time.sleep(wait)
                        ticker_obj = yf.Ticker(meta["yf_symbol"])  # fresh object on retry
                    else:
                        logger.warning("Could not fetch funds data for %s: %s", meta["ticker"], e)
                        break  # non-retryable error — skip holdings/sectors, still do performance

            # Holdings
            holdings: list[dict] = []
            if top_h is not None and not top_h.empty:
                for sym, row in top_h.iterrows():
                    # Use the ticker symbol as instrument identifier (<=12 chars,
                    # consistent across ETFs so overlap analysis works correctly)
                    ident = str(sym).strip()[:12]
                    pct = float(row["Holding Percent"]) * 100  # fraction -> %
                    if pct <= 0:
                        continue
                    holdings.append({
                        "isin": ident,
                        "name": str(row["Name"]).strip()[:200],
                        "weight": round(pct, 4),
                        "country": _lookup_country(ident),
                    })

            # Upsert ETF record
            etf = _upsert_etf(meta, db)

            if holdings:
                result["holdings"] = _upsert_holdings(etf, holdings, as_of, db)
            else:
                result["status"] = "warn"
                result["error"] = "No holdings returned by yfinance"

            result["allocations"] = _upsert_allocations(etf, sector_w, holdings, as_of, db)
            result["performance"] = _upsert_performance(etf, ticker_obj, db,
                                                          perf_yf_symbol=meta.get("perf_yf_symbol"))

            db.commit()
            logger.info("%s: %d holdings, %d allocations, %d perf rows",
                        meta["ticker"], result["holdings"], result["allocations"], result["performance"])

        except Exception as exc:
            db.rollback()
            logger.exception("Failed to import %s", meta["ticker"])
            result["status"] = "error"
            result["error"] = str(exc)

        results.append(result)

    imported = sum(1 for r in results if r["status"] == "ok")
    total_holdings = sum(r["holdings"] for r in results)
    return {
        "imported": imported,
        "total": len(targets),
        "total_holdings": total_holdings,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Daily price refresh (incremental — does NOT delete existing rows)
# ---------------------------------------------------------------------------

# Fallback lookup for ISHares catalogue ETFs that were imported before the
# EODHD symbol was stored in listings (old yfinance-based import path).
_YF_PERF_SYMBOL: dict[str, str] = {
    m["ticker"]: m.get("perf_yf_symbol") or m["yf_symbol"]
    for m in ISHARES_ETFS
}


def _eodhd_symbol_for_etf(etf) -> str | None:
    """
    Return the EODHD-format price symbol for an ETF.
    Priority:
      1. etf.listings["eodhd_symbol"]  — stored during import (all EODHD-imported ETFs)
      2. Catalogue yfinance perf symbol converted to EODHD format (iShares catalogue ETFs)
      3. None (unknown — will fall back to yfinance)
    """
    if etf.listings and etf.listings.get("eodhd_symbol"):
        return etf.listings["eodhd_symbol"]
    yf_sym = _YF_PERF_SYMBOL.get(etf.ticker)
    if yf_sym:
        # Convert yfinance format → EODHD format
        if "." not in yf_sym:
            return yf_sym + ".US"
        if yf_sym.endswith(".L"):
            return yf_sym[:-2] + ".LSE"
        return yf_sym   # .SW, .AS etc. are unchanged
    return None


def _upsert_price_row(db, etf_id, row_date, close: float, currency: str) -> None:
    """Used by the yfinance fallback path in refresh_daily_prices."""
    stmt = pg_insert(Performance).values(
        id=uuid4(),
        etf_id=etf_id,
        date=row_date,
        close_price=round(close, 4),
        currency=currency,
    ).on_conflict_do_update(
        index_elements=["etf_id", "date"],
        set_={"close_price": round(close, 4), "currency": currency},
    )
    db.execute(stmt)


def refresh_daily_prices(db: Session) -> dict:
    """
    Fetch the latest 7 calendar days of closing prices for every ETF in the
    database and upsert into the performance table.  Existing rows are updated
    in-place; no data is deleted.  Designed to be called once per trading day.

    Uses EODHD when EODHD_TOKEN is set (preferred — no rate-limit issues).
    Falls back to yfinance for any ETF where no EODHD token is available.
    """
    import os
    from datetime import datetime, timedelta
    from app.services.etf_import_service import upsert_eodhd_prices

    token = os.getenv("EODHD_TOKEN")
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    etfs = db.query(ETF).order_by(ETF.ticker).all()
    total_rows = 0
    etf_results = []
    errors = []

    for etf in etfs:
        eodhd_sym = _eodhd_symbol_for_etf(etf)
        source = "eodhd" if (token and eodhd_sym) else "yfinance"

        try:
            actual_currency = etf.currency or "USD"

            if token and eodhd_sym:
                # ── EODHD path (shared function) ──────────────────────────
                count = upsert_eodhd_prices(
                    etf_id=etf.id,
                    eodhd_symbol=eodhd_sym,
                    token=token,
                    db=db,
                    from_date=from_date,
                    currency=actual_currency,
                )
            else:
                # ── yfinance fallback ──────────────────────────────────────
                yf_sym = _YF_PERF_SYMBOL.get(etf.ticker, etf.ticker)
                ticker_obj = yf.Ticker(yf_sym)
                hist = ticker_obj.history(period="7d")
                if hist is None or hist.empty:
                    errors.append(f"{etf.ticker}: no data from yfinance ({yf_sym})")
                    continue
                gbx_factor = 1.0
                try:
                    reported = ticker_obj.fast_info.currency or ""
                    if reported:
                        actual_currency = reported
                    if actual_currency in ("GBp", "GBX", "GBx"):
                        gbx_factor = 0.01
                        actual_currency = "GBP"
                except Exception:
                    pass
                count = 0
                for idx, row in hist.iterrows():
                    close = float(row["Close"]) * gbx_factor
                    if close <= 0:
                        continue
                    _upsert_price_row(db, etf.id, idx.date(), close, actual_currency)
                    count += 1

            db.commit()
            total_rows += count
            etf_results.append({"ticker": etf.ticker, "rows_upserted": count, "source": source})
            logger.info("refresh_daily_prices: %s — %d rows via %s", etf.ticker, count, source)

        except Exception as exc:
            db.rollback()
            errors.append(f"{etf.ticker}: {exc}")
            logger.error("refresh_daily_prices failed for %s: %s", etf.ticker, exc)

    return {
        "total_rows_upserted": total_rows,
        "etfs": etf_results,
        "errors": errors,
    }
