"""
price_fetcher_yfinance.py — Fetch historical prices from Yahoo Finance.

Strategy: resolve ISIN -> real ticker via OpenFIGI (free, no auth), then fetch via
yf.Ticker(ticker).history(). This bypasses yfinance's buggy internal ISIN detection
that causes 'RuntimeError: release unlocked lock' in production.
"""

import requests as _requests
import yfinance as yf
from datetime import datetime
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert as pg_insert
import threading
import time

from app.schemas import Performance

_yfinance_lock = threading.Lock()

# OpenFIGI exchange code → Yahoo Finance suffix
_EXCH_TO_YF_SUFFIX = {
    "GY": ".DE",  # Germany (XETRA)
    "GR": ".DE",
    "LN": ".L",   # London
    "NA": ".AS",  # Amsterdam
    "SW": ".SW",  # Switzerland
    "FP": ".PA",  # France
    "IM": ".MI",  # Italy
    "SM": ".MC",  # Spain
    "AV": ".VI",  # Austria
    "BB": ".BR",  # Belgium
    "DC": ".CO",  # Denmark
    "SS": ".ST",  # Sweden
    "HF": ".HE",  # Finland
    "NO": ".OL",  # Norway
}


def fetch_prices_yfinance(
    etf_id,
    isin: str,
    etf_name: str,
    db,
    from_date: str = "2000-01-01",
) -> dict:
    """
    Fetch historical prices from Yahoo Finance for an ETF by ISIN.
    
    yfinance supports ISIN lookup directly via yf.Ticker(isin).history().
    This avoids the internal ISIN lookup bug in yf.download().
    
    Args:
        etf_id: UUID of the ETF in database
        isin: ISIN code (preferred for lookup)
        etf_name: Fallback name if ISIN lookup fails
        db: SQLAlchemy session
        from_date: Start date for historical prices (YYYY-MM-DD)
    
    Returns:
        {
            "success": bool,
            "ticker": str or None,  # The ISIN or name used
            "price_count": int,     # Number of prices upserted
            "message": str,         # Status message
            "error": str or None,   # Error message if failed
        }
    """
    try:
        print(f"\n[yfinance] Starting price fetch for ISIN {isin}, name: {etf_name}")
        
        prices = []
        ticker_used = None
        
        # Step 1: Resolve ISIN → real tickers via OpenFIGI (free, no auth required).
        # This avoids passing an ISIN to yf.Ticker(), which triggers a buggy internal
        # ISIN lookup path causing 'RuntimeError: release unlocked lock' in production.
        print(f"[yfinance] Step 1: Resolving ISIN {isin} via OpenFIGI...")
        candidates = _get_openfigi_candidates(isin)
        print(f"[yfinance] OpenFIGI returned {len(candidates)} candidates: {candidates}")
        
        for candidate in candidates:
            print(f"[yfinance] Trying {candidate}...")
            try:
                prices = _fetch_yfinance_prices_by_ticker(candidate, from_date)
                if prices:
                    ticker_used = candidate
                    print(f"[yfinance] ✓ Got {len(prices)} prices for {candidate}")
                    break
                else:
                    print(f"[yfinance] No data for {candidate}, trying next...")
                    time.sleep(1)  # Avoid rate limits between candidates
            except Exception as e:
                err = str(e)
                print(f"[yfinance] \u2717 {candidate} failed: {type(e).__name__}: {e}")
                if "rate" in err.lower() or "429" in err or "RateLimit" in type(e).__name__:
                    print(f"[yfinance] Rate limited — waiting 5s before next candidate...")
                    time.sleep(5)
                else:
                    time.sleep(1)
        
        if not ticker_used or len(prices) == 0:
            print(f"[yfinance] ✗ Failed to find prices for ISIN {isin}")
            return {
                "success": False,
                "ticker": None,
                "price_count": 0,
                "message": f"Could not find prices for ISIN {isin}",
                "error": "no_price_data",
            }
        
        # Step 3: Upsert prices into database
        print(f"[yfinance] Step 3: Upserting {len(prices)} prices into database...")
        count = _upsert_prices(etf_id, prices, db)
        db.commit()
        
        print(f"[yfinance] ✓ Success! Upserted {count} prices")
        detected_currency = prices[0]["currency"] if prices else None
        return {
            "success": True,
            "ticker": ticker_used,
            "price_count": count,
            "currency": detected_currency,
            "message": f"Fetched {count} prices from Yahoo Finance for {ticker_used}",
            "error": None,
        }
    
    except Exception as e:
        print(f"[yfinance] ✗ Exception in fetch_prices_yfinance: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "ticker": None,
            "price_count": 0,
            "message": f"Error fetching prices: {str(e)}",
            "error": str(e),
        }


def _get_openfigi_candidates(isin: str) -> list[str]:
    """
    Return all Yahoo Finance ticker candidates for an ISIN via OpenFIGI.
    
    OpenFIGI is free and requires no API key for basic usage.
    Returns multiple candidates to try; caller iterates until one has data.
    """
    try:
        resp = _requests.post(
            "https://api.openfigi.com/v3/mapping",
            json=[{"idType": "ID_ISIN", "idValue": isin}],
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[yfinance] OpenFIGI HTTP {resp.status_code} for {isin}")
            return []
        
        data = resp.json()
        results = data[0].get("data") if data else None
        if not results:
            print(f"[yfinance] OpenFIGI: no results for {isin}")
            return []
        
        # ETF/ETP entries first
        ordered = sorted(results, key=lambda r: 0 if r.get("securityType") in ("ETP", "ETF") else 1)
        
        seen: set[str] = set()
        candidates: list[str] = []
        for result in ordered:
            ticker = result.get("ticker")
            exch = result.get("exchCode", "")
            if not ticker:
                continue
            suffix = _EXCH_TO_YF_SUFFIX.get(exch)
            if suffix is None and exch:
                continue  # Unknown exchange — skip
            yf_ticker = f"{ticker}{suffix}" if suffix else ticker
            if yf_ticker not in seen:
                seen.add(yf_ticker)
                candidates.append(yf_ticker)
                print(f"[yfinance] OpenFIGI candidate: {yf_ticker} ({result.get('name')}, exch={exch})")
        
        return candidates
    except Exception as e:
        print(f"[yfinance] OpenFIGI error: {e}")
        return []












def _fetch_yfinance_prices_by_ticker(ticker: str, from_date: str) -> list[dict]:
    """
    Fetch daily historical prices from Yahoo Finance using yf.Ticker().history().
    
    This approach works with ISINs and ticker symbols.
    Avoids the buggy yf.download(isin) path that triggers internal ISIN lookup.
    
    Returns list of dicts with keys: date, close_price, currency
    Thread-safe: uses lock to prevent yfinance threading issues.
    """
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.now()
        
        print(f"[yfinance] Creating Ticker object for {ticker}...")
        
        # Use lock to ensure thread-safe yf.Ticker() call
        with _yfinance_lock:
            ticker_obj = yf.Ticker(ticker)
            print(f"[yfinance] Downloading history for {ticker}...")
            data = ticker_obj.history(start=start, end=end, interval="1d")
            # fast_info.currency is populated after history() and needs no extra request
            try:
                currency = (ticker_obj.fast_info.currency or "USD").upper()
            except Exception:
                currency = "USD"
        
        print(f"[yfinance] Currency for {ticker}: {currency}")
        
        if data is None or data.empty:
            print(f"[yfinance] No data returned for {ticker}")
            return []
        
        print(f"[yfinance] Downloaded {len(data)} rows for {ticker}")
        
        prices = []
        for date, row in data.iterrows():
            try:
                # Get close price (Adj Close preferred, fallback to Close)
                close = None
                if "Adj Close" in data.columns:
                    close = row.get("Adj Close") or row.get("Close")
                else:
                    close = row.get("Close")
                
                if close is None or close == 0 or close <= 0:
                    continue
                
                close = float(close)
                date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
                
                prices.append({
                    "date": date_str,
                    "close_price": round(close, 4),
                    "currency": currency,
                })
            except Exception as row_err:
                print(f"[yfinance] Error processing row {date}: {row_err}")
                continue
        
        print(f"[yfinance] Processed {len(prices)} valid prices for {ticker}")
        return prices
    
    except Exception as e:
        print(f"[yfinance] Error fetching prices for {ticker}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


def _upsert_prices(etf_id, prices: list[dict], db) -> int:
    """
    Upsert prices into the Performance table.
    
    Returns the count of upserted rows.
    """
    from datetime import date as date_type
    
    if not prices:
        return 0
    
    try:
        upserted = 0
        for price in prices:
            stmt = pg_insert(Performance).values(
                etf_id=etf_id,
                date=price["date"],
                close_price=Decimal(str(price["close_price"])),
                currency=price.get("currency", "USD"),
            ).on_conflict_do_update(
                index_elements=["etf_id", "date"],
                set_={
                    "close_price": Decimal(str(price["close_price"])),
                    "currency": price.get("currency", "USD"),
                }
            )
            db.execute(stmt)
            upserted += 1
        
        return upserted
    
    except Exception as e:
        print(f"[yfinance] Error upserting prices: {e}")
        import traceback
        traceback.print_exc()
        return 0
