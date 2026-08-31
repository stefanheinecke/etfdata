"""
price_fetcher_yfinance.py — Fetch historical prices from Yahoo Finance using ISIN lookup.

Uses yf.Ticker(isin).history() for thread-safe ISIN lookups.
"""

import yfinance as yf
from datetime import datetime
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
        
        # Step 1: Try ISIN lookup via yf.Ticker(isin).history()
        # This avoids the buggy internal ISIN lookup in yf.download()
        print(f"[yfinance] Step 1: Trying ISIN {isin}...")
        try:
            prices = _fetch_yfinance_prices_by_ticker(isin, from_date)
            if prices and len(prices) > 0:
                ticker_used = isin
                print(f"[yfinance] ✓ ISIN lookup worked! Got {len(prices)} prices")
        except Exception as e:
            print(f"[yfinance] ✗ ISIN lookup failed: {type(e).__name__}: {e}")
        
        # Step 2: Fallback to name search if ISIN lookup fails
        if not ticker_used and etf_name:
            print(f"[yfinance] Step 2: Trying name lookup for '{etf_name}'...")
            try:
                prices = _fetch_yfinance_prices_by_ticker(etf_name, from_date)
                if prices and len(prices) > 0:
                    ticker_used = etf_name
                    print(f"[yfinance] ✓ Name lookup worked! Got {len(prices)} prices")
            except Exception as e:
                print(f"[yfinance] ✗ Name lookup failed: {type(e).__name__}: {e}")
        
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
        return {
            "success": True,
            "ticker": ticker_used,
            "price_count": count,
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


# All ISIN lookups now use yf.Ticker(isin).history() which works directly











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
                    "currency": "USD",
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
