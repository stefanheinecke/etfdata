"""
add_etf.py — register a new iShares ETF in the database and upload its holdings.

Fetches name, currency, TER, and fund size from yfinance when not supplied.
Also uploads 1 year of daily performance data.  All metadata can be
overridden via flags; sensible iShares defaults are applied.

Usage:
    # Known ticker — downloads holdings CSV automatically, no --csv needed:
    python add_etf.py --ticker SWDA --isin IE00B4L5Y983 \\
        --db "postgresql://user:pass@host:5432/railway"

    # Unknown ticker — provide a direct download URL:
    python add_etf.py --ticker CSNKY --isin IE00B52MJD48 \\
        --download-url "https://www.ishares.com/uk/individual/en/products/{id}/{SLUG}/1467271812596.ajax?tab=all&fileType=csv" \\
        --db "postgresql://..."

    # Use a pre-downloaded local CSV:
    python add_etf.py --ticker IEDY --isin IE00B652H904 --csv IEDY_holdings.csv \\
        --db "postgresql://..."

    # Override auto-fetched fields:
    python add_etf.py --ticker IEDY --isin IE00B0M63177 \\
        --name "iShares MSCI EM UCITS ETF" --ter 0.18 --benchmark "MSCI Emerging Markets" \\
        --db "postgresql://..."

How to find the iShares download URL:
    1. Open the ETF product page on ishares.com
    2. Right-click the "Download" button next to Holdings
    3. Copy the link address — it matches the pattern above
"""

import argparse
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from app.schemas import ETF, Performance
from app.services.ishares_import import ISHARES_ETFS


# ---------------------------------------------------------------------------
# Holdings CSV download
# ---------------------------------------------------------------------------

def _download_holdings(url: str, ticker: str, save_path: str = None) -> str:
    """
    Download an iShares holdings CSV from *url* using browser-like headers.
    Saves the file to *save_path* if given, otherwise to
    {TICKER}_holdings_{today}.csv in the current working directory.
    Returns the path to the saved file.
    """
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/csv,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.ishares.com/",
    }

    print(f"Downloading holdings CSV ...")
    print(f"  URL: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error: {exc}")

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} — download failed.")

    # iShares sometimes returns an HTML login/cookie wall instead of CSV
    content_type = resp.headers.get("Content-Type", "")
    text_start = resp.content[:200].decode("utf-8", errors="ignore").lstrip()
    if "html" in content_type.lower() or text_start.lower().startswith("<!doctype"):
        raise RuntimeError(
            "iShares returned an HTML page instead of a CSV.\n"
            "  The URL may require an active browser session or has changed.\n"
            "  → Open the URL in a browser, download the file manually, then pass --csv <file>."
        )

    if save_path is None:
        save_path = f"{ticker.upper()}_holdings_{date.today().isoformat()}.csv"

    with open(save_path, "wb") as fh:
        fh.write(resp.content)

    print(f"  Saved {len(resp.content):,} bytes → {save_path}")
    return save_path


# ---------------------------------------------------------------------------
# yfinance metadata fetch
# ---------------------------------------------------------------------------

def _fetch_yf_meta(yf_symbol: str) -> dict:
    """
    Return metadata dict from yfinance .info using the correct exchange-suffixed symbol.
    Keys: name, currency, ter (%), fund_size (int), ticker_obj
    """
    try:
        import yfinance as yf
        t = yf.Ticker(yf_symbol)
        info = t.info or {}
        ter_raw = info.get("totalExpenseRatio")          # decimal, e.g. 0.002 = 0.20%
        ter_pct = round(float(ter_raw) * 100, 4) if ter_raw else None
        fund_size = info.get("totalAssets")
        return {
            "name":       info.get("longName") or info.get("shortName") or "",
            "currency":   info.get("currency") or "",
            "ter":        ter_pct,
            "fund_size":  int(fund_size) if fund_size else None,
            "ticker_obj": t,
        }
    except Exception as exc:
        print(f"  yfinance lookup failed for '{yf_symbol}' ({exc})")
        return {}


def _upload_performance(etf: ETF, ticker_obj, currency: str, db) -> int:
    """Fetch 1Y of daily close prices and upsert into the performance table."""
    hist = ticker_obj.history(period="1y")
    if hist is None or hist.empty:
        print("  No historical price data available from yfinance.")
        return 0

    db.query(Performance).filter_by(etf_id=etf.id).delete()
    count = 0
    for idx, row in hist.iterrows():
        close = float(row["Close"])
        if close <= 0:
            continue
        div = float(row.get("Dividends", 0) or 0)
        db.add(Performance(
            etf_id=etf.id,
            date=idx.date(),
            close_price=round(close, 4),
            dividend=round(div, 6) if div else None,
            currency=currency[:3].upper(),
        ))
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register an iShares ETF and upload its holdings CSV."
    )
    # Required
    parser.add_argument("--ticker", required=True,
                        help="ETF ticker symbol (e.g. SWDA, IEDY)")
    parser.add_argument("--isin", required=True,
                        help="ETF's own ISIN (e.g. IE00B4L5Y983)")
    parser.add_argument("--yf-symbol", default=None, dest="yf_symbol",
                        help="Yahoo Finance symbol with exchange suffix (e.g. SWDA.L, CSSPX.SW). "
                             "Auto-resolved from built-in list; only needed for unlisted ETFs.")
    parser.add_argument("--csv", default=None,
                        help="Path to the iShares holdings CSV file. "
                             "If omitted the file is downloaded automatically "
                             "(requires --download-url or a known ticker in the built-in list).")
    parser.add_argument("--download-url", default=None, dest="download_url",
                        help="Direct URL to the iShares holdings CSV download page. "
                             "Auto-resolved from built-in list for known tickers; "
                             "only needed for unlisted ETFs. "
                             "URL pattern (UK): https://www.ishares.com/uk/individual/en/products/{id}/{SLUG}/1467271812596.ajax?tab=all&fileType=csv")
    parser.add_argument("--db", default=None,
                        help="DATABASE_URL (overrides DATABASE_PUBLIC_URL env var)")

    # Optional overrides
    parser.add_argument("--name", default=None,
                        help="Full ETF name (auto-fetched from yfinance if omitted)")
    parser.add_argument("--provider", default="iShares",
                        help="Fund provider (default: iShares)")
    parser.add_argument("--domicile", default="IE",
                        help="Fund domicile ISO-2 (default: IE)")
    parser.add_argument("--currency", default=None,
                        help="Base currency (auto-fetched from yfinance if omitted)")
    parser.add_argument("--ter", default=None, type=float,
                        help="Total Expense Ratio in %% (e.g. 0.20). Auto-fetched if omitted.")
    parser.add_argument("--fund-size", default=None, type=int, dest="fund_size",
                        help="Fund AUM in base currency. Auto-fetched if omitted.")
    parser.add_argument("--benchmark", default=None,
                        help="Benchmark index name (e.g. 'MSCI World')")
    parser.add_argument("--replication", default="Physical", dest="replication_method",
                        help="Replication method (default: Physical)")
    parser.add_argument("--no-country", action="store_true",
                        help="Skip yfinance country lookups during holdings upload (faster)")
    parser.add_argument("--no-performance", action="store_true",
                        help="Skip uploading historical performance data")
    args = parser.parse_args()

    db_url = args.db or os.environ.get("DATABASE_PUBLIC_URL")
    if not db_url:
        sys.exit("ERROR: Provide --db or set DATABASE_PUBLIC_URL environment variable.")

    # -- Resolve yfinance symbol and any known defaults from ISHARES_ETFS --
    ticker_upper = args.ticker.strip().upper()
    known = next((e for e in ISHARES_ETFS if e["ticker"] == ticker_upper), None)
    yf_symbol = args.yf_symbol or (known["yf_symbol"] if known else args.ticker)
    known_ter       = known["ter"]       if known else None
    known_benchmark = known["benchmark"] if known else None
    known_url       = known.get("holdings_url") if known else None
    print(f"Using yfinance symbol: {yf_symbol}")

    # -- Resolve holdings CSV (download if --csv not provided) --
    csv_path = args.csv
    if csv_path is None:
        download_url = args.download_url or known_url
        if download_url is None:
            sys.exit(
                "ERROR: No holdings CSV provided.\n"
                "  Pass --csv <file> to use a local file, or\n"
                "  pass --download-url <url> to download from iShares, or\n"
                "  add the ticker to the built-in ISHARES_ETFS list with a holdings_url."
            )
        try:
            csv_path = _download_holdings(download_url, args.ticker)
        except RuntimeError as exc:
            sys.exit(f"ERROR downloading holdings: {exc}")

    # -- Fetch metadata from yfinance --
    print(f"Fetching metadata for {args.ticker} from yfinance ...")
    yf_meta = _fetch_yf_meta(yf_symbol)

    name       = args.name      or yf_meta.get("name")      or args.ticker
    currency   = args.currency  or yf_meta.get("currency")  or "USD"
    # CLI flag > yfinance > known list fallback
    ter        = args.ter       if args.ter is not None      else (yf_meta.get("ter") or known_ter)
    fund_size  = args.fund_size if args.fund_size is not None else yf_meta.get("fund_size")
    benchmark  = args.benchmark or known_benchmark

    print(f"  name:        {name}")
    print(f"  currency:    {currency}")
    print(f"  ter:         {ter}%"       if ter        else "  ter:         (not found)")
    print(f"  fund_size:   {fund_size:,}" if fund_size  else "  fund_size:   (not found)")
    print(f"  benchmark:   {benchmark}" if benchmark else "  benchmark:   (not provided - pass --benchmark)")
    print(f"  replication: {args.replication_method}")

    # -- Connect to DB --
    engine = create_engine(db_url, echo=False, poolclass=NullPool, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        existing = db.query(ETF).filter(ETF.ticker == args.ticker.strip().upper()).first()
        if existing:
            # Update all resolvable fields so re-running the script refreshes metadata
            existing.name              = name[:255]
            existing.replication_method = args.replication_method or existing.replication_method
            if ter is not None:
                existing.ter           = Decimal(str(ter))
            if fund_size is not None:
                existing.fund_size     = fund_size
            if benchmark:
                existing.benchmark     = benchmark
            if currency:
                existing.currency      = currency[:3].upper()
            db.commit()
            db.refresh(existing)
            etf = existing
            print(f"\nUpdated ETF: {etf.name} ({etf.ticker}), id={etf.id}")
        else:
            etf = ETF(
                isin=args.isin.strip().upper(),
                ticker=args.ticker.strip().upper(),
                name=name[:255],
                provider=args.provider,
                domicile=args.domicile.strip().upper(),
                replication_method=args.replication_method,
                ter=Decimal(str(ter)) if ter is not None else None,
                fund_size=fund_size,
                benchmark=benchmark,
                currency=currency[:3].upper(),
            )
            db.add(etf)
            db.commit()
            db.refresh(etf)
            print(f"\nCreated ETF: {etf.name} ({etf.ticker}), id={etf.id}")

        # -- Performance data --
        if not args.no_performance:
            ticker_obj = yf_meta.get("ticker_obj")
            if ticker_obj is not None:
                print(f"\nUploading performance data ...")
                perf_count = _upload_performance(etf, ticker_obj, currency, db)
                db.commit()
                print(f"  Inserted {perf_count} daily price records.")
            else:
                print("\nSkipping performance data (yfinance unavailable).")

    except Exception as exc:
        db.rollback()
        db.close()
        sys.exit(f"ERROR: {exc}")
    finally:
        db.close()

    # -- Upload holdings via upload.py --
    print(f"\nUploading holdings from {csv_path} ...")
    upload_script = os.path.join(os.path.dirname(__file__), "upload.py")
    cmd = [
        sys.executable, upload_script,
        "--csv", csv_path,
        "--ticker", args.ticker,
        "--db", db_url,
    ]
    if args.no_country:
        cmd.append("--no-country")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
