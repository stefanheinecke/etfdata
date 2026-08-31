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
        # Step 1: Try to find ticker by ISIN (try direct ISIN first)
        ticker = None
        
        # Try direct ISIN first (this often works for yfinance)
        try:
            prices = _fetch_yfinance_prices(isin, from_date)
            if prices and len(prices) > 0:
                ticker = isin
        except:
            pass
        
        # Step 2: If direct ISIN didn't work, try exchange suffixes
        if not ticker:
            ticker = _lookup_ticker_by_isin(isin)
        
        # Step 3: Fallback to name search if ISIN lookup fails
        if not ticker and etf_name:
            ticker = _lookup_ticker_by_name(etf_name)
        
        if not ticker:
            return {
                "success": False,
                "ticker": None,
                "price_count": 0,
                "message": f"Could not find Yahoo Finance ticker for ISIN {isin}",
                "error": "ticker_not_found",
            }
        
        # Step 3: Fetch prices from Yahoo Finance (if not already fetched above)
        if ticker == isin:
            prices = _fetch_yfinance_prices(isin, from_date)
        else:
            prices = _fetch_yfinance_prices(ticker, from_date)
        
        if not prices or len(prices) == 0:
            return {
                "success": False,
                "ticker": ticker,
                "price_count": 0,
                "message": f"No price data found for {ticker}",
                "error": "no_price_data",
            }
        
        # Step 4: Upsert prices into database
        count = _upsert_prices(etf_id, prices, db)
        db.commit()
        
        return {
            "success": True,
            "ticker": ticker,
            "price_count": count,
            "message": f"Fetched {count} prices from Yahoo Finance for {ticker}",
            "error": None,
        }
    
    except Exception as e:
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
            return []
        
        # Ensure we have a proper DataFrame (yfinance may return Series for single ticker)
        if not isinstance(data.index, type(data.index)):
            # Single column, wrap in DataFrame
            data = data.to_frame()
        
        prices = []
        for date, row in data.iterrows():
            close = float(row.get("Close") or row.get("Adj Close") or 0)
            
            if close <= 0:
                continue
            
            prices.append({
                "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10],
                "close_price": round(close, 4),
                "currency": "USD",  # Yahoo Finance returns USD for most ETFs
            })
        
        return prices
    
    except Exception as e:
        print(f"Error fetching prices from Yahoo Finance: {e}")
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
