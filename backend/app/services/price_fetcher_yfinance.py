"""
price_fetcher_yfinance.py — Fetch historical prices from Yahoo Finance using ISIN or ETF name.

Provides a fallback when EODHD symbol is not available. Handles ISIN lookup and price fetching.
"""

import yfinance as yf
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.dialects.postgresql import insert as pg_insert
import threading

from app.schemas import Performance

# Thread lock to ensure thread-safe access to yfinance
# (yfinance has internal threading issues when called from multiple threads)
_yfinance_lock = threading.Lock()


def fetch_prices_yfinance(
    etf_id,
    isin: str,
    etf_name: str,
    db,
    from_date: str = "2000-01-01",
) -> dict:
    """
    Fetch historical prices from Yahoo Finance for an ETF by ISIN or name.
    
    Args:
        etf_id: UUID of the ETF in database
        isin: ISIN code (preferred for lookup)
        etf_name: Fallback name if ISIN lookup fails
        db: SQLAlchemy session
        from_date: Start date for historical prices (YYYY-MM-DD)
    
    Returns:
        {
            "success": bool,
            "ticker": str or None,  # The Yahoo Finance ticker found
            "price_count": int,     # Number of prices upserted
            "message": str,         # Status message
            "error": str or None,   # Error message if failed
        }
    """
    try:
        print(f"\n[yfinance] Starting price fetch for ISIN {isin}, name: {etf_name}")
        
        # Step 1: Try to find ticker by ISIN with exchange suffixes
        # NOTE: Skip direct ISIN download - yfinance has a bug with ISIN lookups
        ticker = None
        prices = []
        
        print(f"[yfinance] Step 1: Trying ISIN with exchange suffixes...")
        ticker = _lookup_ticker_by_isin(isin)
        if ticker:
            print(f"[yfinance] ✓ Found ticker with suffixes: {ticker}")
        
        # Step 2: Fallback to name search if ISIN lookup fails
        if not ticker and etf_name:
            print(f"[yfinance] Step 2: Trying name lookup for '{etf_name}'...")
            ticker = _lookup_ticker_by_name(etf_name)
            if ticker:
                print(f"[yfinance] ✓ Found ticker by name: {ticker}")
        
        if not ticker:
            print(f"[yfinance] ✗ Failed to find ticker for ISIN {isin}")
            return {
                "success": False,
                "ticker": None,
                "price_count": 0,
                "message": f"Could not find Yahoo Finance ticker for ISIN {isin}",
                "error": "ticker_not_found",
            }
        
        # Step 3: Fetch prices from Yahoo Finance
        print(f"[yfinance] Step 3: Fetching prices for ticker {ticker}...")
        prices = _fetch_yfinance_prices(ticker, from_date)
        
        if not prices or len(prices) == 0:
            print(f"[yfinance] ✗ No price data found for {ticker}")
            return {
                "success": False,
                "ticker": ticker,
                "price_count": 0,
                "message": f"No price data found for {ticker}",
                "error": "no_price_data",
            }
        
        # Step 4: Upsert prices into database
        print(f"[yfinance] Step 4: Upserting {len(prices)} prices into database...")
        count = _upsert_prices(etf_id, prices, db)
        db.commit()
        
        print(f"[yfinance] ✓ Success! Upserted {count} prices")
        return {
            "success": True,
            "ticker": ticker,
            "price_count": count,
            "message": f"Fetched {count} prices from Yahoo Finance for {ticker}",
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


def _lookup_ticker_by_isin(isin: str) -> str | None:
    """
    Look up a Yahoo Finance ticker by ISIN code.
    
    Uses thread lock to ensure safe access to yfinance API.
    Tries multiple exchange suffixes to find the ticker.
    """
    if not isin or len(isin) < 12:
        return None
    
    try:
        # Try common exchange suffixes for the ISIN
        # Order: prefer liquid markets (LSE, Xetra, US, Amsterdam, Swiss, Milan, Paris, Madrid, Lisbon, etc.)
        # NOTE: Skip bare ISIN (yfinance has internal ISIN lookup bug)
        exchange_suffixes = [
            ".L",    # London Stock Exchange
            ".DE",   # Xetra (Germany)
            ".US",   # NYSE/NASDAQ
            ".AS",   # Euronext Amsterdam
            ".SW",   # SIX Swiss Exchange
            ".MI",   # Borsa Italiana
            ".PA",   # Euronext Paris
            ".MA",   # Euronext Madrid
            ".LI",   # Euronext Lisbon
            ".BR",   # Euronext Brussels
            ".AX",   # ASX (Australia)
            ".NZ",   # NZX (New Zealand)
            ".TO",   # TSX (Toronto)
            ".V",    # TSX Venture (Canada)
            ".OL",   # Oslo Stock Exchange
            ".ST",   # Nasdaq Stockholm
            ".HE",   # Nasdaq Helsinki
            ".CO",   # Nasdaq Copenhagen
            ".VX",   # SIX (alternate)
        ]
        
        for suffix in exchange_suffixes:
            test_ticker = isin + suffix
            try:
                # Use lock to ensure thread-safe yf.Ticker() calls
                with _yfinance_lock:
                    test_obj = yf.Ticker(test_ticker)
                    if test_obj.info and test_obj.info.get("shortName"):
                        return test_ticker
            except Exception as e:
                print(f"[yfinance] Ticker {test_ticker} not found: {type(e).__name__}")
                continue
        
        return None
    
    except Exception:
        return None


def _lookup_ticker_by_name(name: str) -> str | None:
    """
    Look up a Yahoo Finance ticker by ETF name (fallback method).
    
    This is less reliable; ISIN lookup is preferred.
    Uses thread lock for safe API access.
    """
    if not name or len(name) < 3:
        return None
    
    try:
        # Use lock to ensure thread-safe yf.Ticker() calls
        with _yfinance_lock:
            ticker_obj = yf.Ticker(name)
            if ticker_obj.info and ticker_obj.info.get("shortName"):
                return name
        
        return None
    
    except Exception:
        return None


def _fetch_yfinance_prices(ticker: str, from_date: str) -> list[dict]:
    """
    Fetch daily historical prices from Yahoo Finance.
    
    Returns list of dicts with keys: date, close_price, currency
    Thread-safe: uses lock to prevent yfinance threading issues.
    """
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.now()
        
        # Use lock to ensure thread-safe access to yfinance
        # Set auto_adjust=False to skip problematic internal ISIN lookups
        with _yfinance_lock:
            print(f"[yfinance] Downloading data for {ticker}...")
            data = yf.download(
                ticker, 
                start=start, 
                end=end, 
                interval="1d", 
                progress=False,
                auto_adjust=False  # Avoids yfinance's problematic cookie/session operations
            )
        
        if data is None or data.empty:
            print(f"[yfinance] No data returned for {ticker}")
            return []
        
        print(f"[yfinance] Downloaded {len(data)} rows for {ticker}")
        print(f"[yfinance] DataFrame shape: {data.shape}, columns: {list(data.columns)}")
        
        prices = []
        for date, row in data.iterrows():
            try:
                # Try different ways to get the close price
                close = None
                if isinstance(row, dict):
                    close = row.get("Close") or row.get("Adj Close")
                else:
                    # pandas Series
                    if "Close" in row.index:
                        close = row["Close"]
                    elif "Adj Close" in row.index:
                        close = row["Adj Close"]
                
                if close is None:
                    continue
                
                close = float(close)
                if close <= 0:
                    continue
                
                date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
                prices.append({
                    "date": date_str,
                    "close_price": round(close, 4),
                    "currency": "USD",
                })
            except Exception as row_err:
                print(f"[yfinance] Error processing row {date}: {row_err}")
                continue
        
        print(f"[yfinance] Processed {len(prices)} valid prices for {ticker}")
        return prices
    
    except Exception as e:
        print(f"[yfinance] Error fetching prices from Yahoo Finance for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return []


def _upsert_prices(etf_id, prices: list[dict], db) -> int:
    """
    Upsert prices into the Performance table.
    """
    from datetime import date as date_type
    
    count = 0
    for price_data in prices:
        try:
            stmt = pg_insert(Performance).values(
                id=uuid4(),
                etf_id=etf_id,
                date=date_type.fromisoformat(price_data["date"]),
                close_price=price_data["close_price"],
                currency=price_data["currency"],
            ).on_conflict_do_update(
                index_elements=["etf_id", "date"],
                set_={"close_price": price_data["close_price"], "currency": price_data["currency"]},
            )
            db.execute(stmt)
            count += 1
        except Exception as e:
            print(f"Error upserting price: {e}")
            continue
    
    return count
