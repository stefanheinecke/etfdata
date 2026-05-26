"""
add_etf.py — register a new iShares ETF in the database and upload its holdings.

Fetches name, currency, TER, and fund size from yfinance when not supplied.
Also uploads 1 year of daily performance data.  All metadata can be
overridden via flags; sensible iShares defaults are applied.

Usage:
    python add_etf.py --ticker SWDA --isin IE00B4L5Y983 --csv SWDA_holdings.csv \\
        --db "postgresql://user:pass@host:5432/railway"

    # Override auto-fetched / default fields:
    python add_etf.py --ticker IEDY --isin IE00B0M63177 --csv SEDY_holdings.csv \\
        --name "iShares MSCI EM UCITS ETF" --ter 0.18 --benchmark "MSCI Emerging Markets" \\
        --db "postgresql://..."
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


# ---------------------------------------------------------------------------
# yfinance metadata fetch
# ---------------------------------------------------------------------------

def _fetch_yf_meta(ticker: str) -> dict:
    """
    Return metadata dict from yfinance .info.
    Keys: name, currency, ter (%), fund_size (int), ticker_obj
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
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
        print(f"  yfinance lookup failed ({exc})")
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
    parser.add_argument("--csv", required=True,
                        help="Path to the iShares holdings CSV file")
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

    # -- Fetch metadata from yfinance --
    print(f"Fetching metadata for {args.ticker} from yfinance ...")
    yf_meta = _fetch_yf_meta(args.ticker)

    name       = args.name      or yf_meta.get("name")      or args.ticker
    currency   = args.currency  or yf_meta.get("currency")  or "USD"
    ter        = args.ter       if args.ter is not None      else yf_meta.get("ter")
    fund_size  = args.fund_size if args.fund_size is not None else yf_meta.get("fund_size")

    print(f"  name:        {name}")
    print(f"  currency:    {currency}")
    print(f"  ter:         {ter}%"       if ter        else "  ter:         (not found)")
    print(f"  fund_size:   {fund_size:,}" if fund_size  else "  fund_size:   (not found)")
    print(f"  benchmark:   {args.benchmark}" if args.benchmark else "  benchmark:   (not provided - pass --benchmark)")
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
            if args.benchmark:
                existing.benchmark     = args.benchmark
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
                benchmark=args.benchmark,
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
    print(f"\nUploading holdings from {args.csv} ...")
    upload_script = os.path.join(os.path.dirname(__file__), "upload.py")
    cmd = [
        sys.executable, upload_script,
        "--csv", args.csv,
        "--ticker", args.ticker,
        "--db", db_url,
    ]
    if args.no_country:
        cmd.append("--no-country")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
