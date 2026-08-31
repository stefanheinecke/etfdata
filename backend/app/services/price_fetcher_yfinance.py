"""
price_fetcher_yfinance.py — Fetch historical prices from Yahoo Finance using ISIN or ETF name.

Provides a fallback when EODHD symbol is not available. Handles ISIN lookup and price fetching.
"""

import yfinance as yf
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.schemas import Performance


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
        
        # Step 1: Try to find ticker by ISIN (try direct ISIN first)
        ticker = None
        prices = []
        
        # Try direct ISIN first (this often works for yfinance)
        print(f"[yfinance] Step 1: Trying direct ISIN {isin}...")
        try:
            prices = _fetch_yfinance_prices(isin, from_date)
            if prices and len(prices) > 0:
                ticker = isin
                print(f"[yfinance] ✓ Direct ISIN worked! Got {len(prices)} prices")
        except Exception as e:
            print(f"[yfinance] ✗ Direct ISIN failed: {e}")
        
        # Step 2: If direct ISIN didn't work, try exchange suffixes
        if not ticker:
            print(f"[yfinance] Step 2: Trying ISIN with exchange suffixes...")
            ticker = _lookup_ticker_by_isin(isin)
            if ticker:
                print(f"[yfinance] ✓ Found ticker with suffixes: {ticker}")
        
        # Step 3: Fallback to name search if ISIN lookup fails
        if not ticker and etf_name:
            print(f"[yfinance] Step 3: Trying name lookup for '{etf_name}'...")
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
        
        # Step 4: Fetch prices from Yahoo Finance (if not already fetched above)
        print(f"[yfinance] Step 4: Fetching prices for ticker {ticker}...")
        if ticker == isin and prices and len(prices) > 0:
            print(f"[yfinance] Using cached prices from direct ISIN fetch")
        else:
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
        
        # Step 5: Upsert prices into database
        print(f"[yfinance] Step 5: Upserting {len(prices)} prices into database...")
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
    
    Uses yfinance's Ticker lookup which accepts ISIN codes for many ETFs.
    Tries multiple exchange suffixes to find the ticker.
    """
    if not isin or len(isin) < 12:
        return None
    
    try:
        # Try direct ISIN lookup first
        ticker_obj = yf.Ticker(isin)
        
        # Check if we got valid data (has info)
        if ticker_obj.info and ticker_obj.info.get("shortName"):
            return isin
        
        # Try common exchange suffixes for the ISIN
        # Order: prefer liquid markets (LSE, Xetra, US, Amsterdam, Swiss, Milan, Paris, Madrid, Lisbon, etc.)
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
                test_obj = yf.Ticker(test_ticker)
                if test_obj.info and test_obj.info.get("shortName"):
                    return test_ticker
            except:
                continue
        
        return None
    
    except Exception:
        return None


def _lookup_ticker_by_name(name: str) -> str | None:
    """
    Look up a Yahoo Finance ticker by ETF name (fallback method).
    
    This is less reliable; ISIN lookup is preferred.
    """
    if not name or len(name) < 3:
        return None
    
    try:
        # Extract key words from name (e.g., "iShares Core FTSE 100" -> try "FTSE100")
        # For now, try the name as-is
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
    """
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.now()
        
        # Fetch daily data
        data = yf.download(ticker, start=start, end=end, interval="1d", progress=False)
        
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
