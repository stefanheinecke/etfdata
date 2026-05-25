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

import yfinance as yf
from sqlalchemy.orm import Session

from app.schemas import ETF, Holding, Allocation, Performance

logger = logging.getLogger(__name__)

# Cache country lookups across ETFs so AAPL / MSFT etc. are only fetched once
_country_cache: dict[str, str] = {}

# yfinance returns full country names; map to ISO-3166-1 alpha-2 codes (VARCHAR(2) in DB)
_COUNTRY_ISO: dict[str, str] = {
    "Australia": "AU", "Austria": "AT", "Belgium": "BE", "Bermuda": "BM",
    "Brazil": "BR", "Canada": "CA", "Cayman Islands": "KY", "Chile": "CL",
    "China": "CN", "Colombia": "CO", "Czech Republic": "CZ", "Denmark": "DK",
    "Egypt": "EG", "Finland": "FI", "France": "FR", "Germany": "DE",
    "Greece": "GR", "Hong Kong": "HK", "Hungary": "HU", "India": "IN",
    "Indonesia": "ID", "Ireland": "IE", "Israel": "IL", "Italy": "IT",
    "Japan": "JP", "Luxembourg": "LU", "Malaysia": "MY", "Mexico": "MX",
    "Netherlands": "NL", "New Zealand": "NZ", "Norway": "NO", "Philippines": "PH",
    "Poland": "PL", "Portugal": "PT", "Qatar": "QA", "Saudi Arabia": "SA",
    "Singapore": "SG", "South Africa": "ZA", "South Korea": "KR", "Spain": "ES",
    "Sweden": "SE", "Switzerland": "CH", "Taiwan": "TW", "Thailand": "TH",
    "Turkey": "TR", "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States": "US", "Vietnam": "VN",
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
    {"yf_symbol": "IVV", "ticker": "IVV", "name": "iShares Core S&P 500 ETF", "isin": "US4642872000", "currency": "USD", "domicile": "US", "ter": 0.03, "replication_method": "Physical", "benchmark": "S&P 500 Index"},
    {"yf_symbol": "IWM", "ticker": "IWM", "name": "iShares Russell 2000 ETF", "isin": "US4642876555", "currency": "USD", "domicile": "US", "ter": 0.19, "replication_method": "Physical", "benchmark": "Russell 2000 Index"},
    {"yf_symbol": "IWF", "ticker": "IWF", "name": "iShares Russell 1000 Growth ETF", "isin": "US4642876308", "currency": "USD", "domicile": "US", "ter": 0.19, "replication_method": "Physical", "benchmark": "Russell 1000 Growth Index"},
    {"yf_symbol": "IWD", "ticker": "IWD", "name": "iShares Russell 1000 Value ETF", "isin": "US4642876316", "currency": "USD", "domicile": "US", "ter": 0.19, "replication_method": "Physical", "benchmark": "Russell 1000 Value Index"},
    {"yf_symbol": "IJH", "ticker": "IJH", "name": "iShares Core S&P Mid-Cap ETF", "isin": "US4642874329", "currency": "USD", "domicile": "US", "ter": 0.05, "replication_method": "Physical", "benchmark": "S&P MidCap 400 Index"},
    {"yf_symbol": "IJR", "ticker": "IJR", "name": "iShares Core S&P Small-Cap ETF", "isin": "US46428V7X74", "currency": "USD", "domicile": "US", "ter": 0.06, "replication_method": "Physical", "benchmark": "S&P SmallCap 600 Index"},
    {"yf_symbol": "EFA", "ticker": "EFA", "name": "iShares MSCI EAFE ETF", "isin": "US4642874659", "currency": "USD", "domicile": "US", "ter": 0.32, "replication_method": "Physical", "benchmark": "MSCI EAFE Index"},
    {"yf_symbol": "EEM", "ticker": "EEM", "name": "iShares MSCI Emerging Markets ETF", "isin": "US4642864657", "currency": "USD", "domicile": "US", "ter": 0.68, "replication_method": "Physical", "benchmark": "MSCI Emerging Markets Index"},
    {"yf_symbol": "AGG", "ticker": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "isin": "US4642872422", "currency": "USD", "domicile": "US", "ter": 0.03, "replication_method": "Physical", "benchmark": "Bloomberg U.S. Aggregate Bond Index"},
    {"yf_symbol": "LQD", "ticker": "LQD", "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF", "isin": "US4642881041", "currency": "USD", "domicile": "US", "ter": 0.14, "replication_method": "Physical", "benchmark": "Markit iBoxx USD Liquid Investment Grade Index"},
    # European UCITS ETFs - Yahoo Finance exchange suffixes required
    {"yf_symbol": "SWDA.L", "ticker": "SWDA", "name": "iShares Core MSCI World UCITS ETF USD (Acc)", "isin": "IE00B4L5Y983", "currency": "USD", "domicile": "IE", "ter": 0.20, "replication_method": "Physical", "benchmark": "MSCI World Index"},
    {"yf_symbol": "CSSPX.SW", "ticker": "CSSPX", "name": "iShares Core S&P 500 UCITS ETF USD (Acc)", "isin": "IE00B5BMR087", "currency": "USD", "domicile": "IE", "ter": 0.07, "replication_method": "Physical", "benchmark": "S&P 500 Index"},
    {"yf_symbol": "IEDY.L", "ticker": "IEDY", "name": "iShares Emerging Markets Dividend UCITS ETF", "isin": "IE00B652H904", "currency": "USD", "domicile": "IE", "ter": 0.65, "replication_method": "Physical", "benchmark": "Dow Jones Emerging Markets Select Dividend Index"},
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
            replication_method=meta["replication_method"],
            ter=meta["ter"],
            currency=meta["currency"],
            benchmark=meta["benchmark"],
        )
        db.add(etf)
        db.flush()
    else:
        etf.ticker = meta["ticker"]
        etf.name = meta["name"]
        etf.replication_method = meta["replication_method"]
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


def _upsert_performance(etf: ETF, ticker_obj: "yf.Ticker", db: Session) -> int:
    hist = ticker_obj.history(period="1y")
    if hist is None or hist.empty:
        return 0
    db.query(Performance).filter_by(etf_id=etf.id).delete()
    count = 0
    for idx, row in hist.iterrows():
        close = float(row["Close"])
        if close <= 0:
            continue
        db.add(Performance(
            etf_id=etf.id,
            date=idx.date(),
            close_price=round(close, 4),
            currency=etf.currency,
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
            result["performance"] = _upsert_performance(etf, ticker_obj, db)

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
