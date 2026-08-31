"""
performance_calculator.py — Calculate ETF performance metrics from price history.

Metrics calculated:
- Total return (from first to last price)
- YTD return (year-to-date)
- 1-year return (if available)
- 3-year annualized return (if available)
- Volatility (annualized)
- Sharpe ratio (assuming risk-free rate)
- Maximum drawdown
"""

from datetime import datetime, timedelta
from decimal import Decimal
import math


def calculate_metrics(prices: list[dict], risk_free_rate: float = 0.025) -> dict:
    """
    Calculate performance metrics from a list of price records.
    
    Args:
        prices: List of dicts with keys: date (str YYYY-MM-DD), close_price (float)
        risk_free_rate: Annual risk-free rate for Sharpe calculation (default 2.5%)
    
    Returns:
        Dict with metrics: {
            'total_return': float,         # % from first to last price
            'ytd_return': float,           # % year-to-date
            'return_1y': float | None,     # % 1-year return (if available)
            'return_3y': float | None,     # % 3-year annualized return (if available)
            'volatility_annual': float,    # % annualized volatility
            'sharpe_ratio': float,         # Sharpe ratio
            'max_drawdown': float,         # % maximum drawdown
            'price_count': int,            # Number of price points
            'date_range': str,             # "YYYY-MM-DD to YYYY-MM-DD"
        }
    """
    if not prices or len(prices) < 2:
        return {
            'total_return': None,
            'ytd_return': None,
            'return_1y': None,
            'return_3y': None,
            'volatility_annual': None,
            'sharpe_ratio': None,
            'max_drawdown': None,
            'price_count': len(prices),
            'date_range': '',
        }
    
    # Sort by date ascending
    prices = sorted(prices, key=lambda p: p['date'])
    
    # Extract prices and dates
    price_list = [float(p['close_price']) for p in prices]
    date_list = [p['date'] for p in prices]
    
    # Parse dates
    try:
        if isinstance(date_list[0], str):
            dates = [datetime.fromisoformat(d).date() for d in date_list]
        else:
            dates = date_list
    except (ValueError, AttributeError):
        dates = date_list
    
    today = datetime.now().date()
    first_date = dates[0]
    last_date = dates[-1]
    
    # ─── Total Return ─────────────────────────────────────────
    first_price = price_list[0]
    last_price = price_list[-1]
    total_return = ((last_price - first_price) / first_price) * 100
    
    # ─── YTD Return ───────────────────────────────────────────
    year_start = datetime(today.year, 1, 1).date()
    ytd_price = None
    for i, d in enumerate(dates):
        if d >= year_start:
            ytd_price = price_list[i]
            break
    
    ytd_return = None
    if ytd_price is not None and ytd_price != 0:
        ytd_return = ((last_price - ytd_price) / ytd_price) * 100
    
    # ─── 1-Year Return ───────────────────────────────────────
    one_year_ago = today - timedelta(days=365)
    one_year_price = None
    for i, d in enumerate(dates):
        if d >= one_year_ago:
            one_year_price = price_list[i]
            break
    
    return_1y = None
    if one_year_price is not None and one_year_price != 0:
        # Only calculate if we have at least 200 days of data in this period
        days_in_period = (last_date - max(dates[0], one_year_ago)).days
        if days_in_period >= 200:
            return_1y = ((last_price - one_year_price) / one_year_price) * 100
    
    # ─── 3-Year Annualized Return ────────────────────────────
    three_years_ago = today - timedelta(days=365 * 3)
    three_year_price = None
    for i, d in enumerate(dates):
        if d >= three_years_ago:
            three_year_price = price_list[i]
            break
    
    return_3y = None
    if three_year_price is not None and three_year_price != 0:
        # Only calculate if we have at least 700 days of data in this period
        days_in_period = (last_date - max(dates[0], three_years_ago)).days
        if days_in_period >= 700:
            total_return_3y = ((last_price - three_year_price) / three_year_price)
            years = days_in_period / 365.25
            if years > 0:
                return_3y = ((total_return_3y + 1) ** (1 / years) - 1) * 100
    
    # ─── Daily Returns & Volatility ────────────────────────────
    daily_returns = []
    for i in range(1, len(price_list)):
        ret = (price_list[i] - price_list[i-1]) / price_list[i-1]
        daily_returns.append(ret)
    
    if daily_returns:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance) if variance > 0 else 0
        volatility_annual = daily_volatility * math.sqrt(252) * 100  # 252 trading days
    else:
        volatility_annual = 0
    
    # ─── Sharpe Ratio ─────────────────────────────────────────
    excess_return = total_return - (risk_free_rate * 100)
    sharpe_ratio = 0
    if volatility_annual > 0:
        sharpe_ratio = excess_return / volatility_annual
    
    # ─── Maximum Drawdown ─────────────────────────────────────
    max_drawdown = 0
    running_max = price_list[0]
    for price in price_list[1:]:
        if price > running_max:
            running_max = price
        drawdown = (price - running_max) / running_max
        if drawdown < max_drawdown:
            max_drawdown = drawdown
    max_drawdown = max_drawdown * 100  # Convert to percentage
    
    return {
        'total_return': round(total_return, 2),
        'ytd_return': round(ytd_return, 2) if ytd_return is not None else None,
        'return_1y': round(return_1y, 2) if return_1y is not None else None,
        'return_3y': round(return_3y, 2) if return_3y is not None else None,
        'volatility_annual': round(volatility_annual, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'max_drawdown': round(max_drawdown, 2),
        'price_count': len(price_list),
        'date_range': f"{first_date.isoformat()} to {last_date.isoformat()}",
    }


def get_price_points_for_chart(prices: list[dict], max_points: int = 250) -> list[dict]:
    """
    Reduce price data to a manageable number of points for charting.
    Takes every Nth point to fit within max_points.
    
    Args:
        prices: List of price dicts with 'date' and 'close_price'
        max_points: Maximum number of points to return
    
    Returns:
        Filtered list of price dicts
    """
    if len(prices) <= max_points:
        return prices
    
    step = len(prices) // max_points
    return prices[::step] + [prices[-1]]  # Always include last point
