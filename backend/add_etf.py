"""
add_etf.py — register a new iShares ETF in the database and upload its holdings.

Fetches ETF name and currency from yfinance when not supplied.  All other
metadata can be passed as flags; sensible iShares defaults are applied.

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
import time
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from app.schemas import ETF


# ---------------------------------------------------------------------------
# yfinance metadata fetch
# ---------------------------------------------------------------------------

def _fetch_yf_meta(ticker: str) -> dict:
    """Return {name, currency} from yfinance, or empty dict on failure."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return {
            "name": info.get("longName") or info.get("shortName") or "",
            "currency": info.get("currency") or "",
        }
    except Exception as exc:
        print(f"  yfinance lookup failed ({exc}) - set --name / --currency manually if needed")
        return {}


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
                        help="Total Expense Ratio in %% (e.g. 0.20)")
    parser.add_argument("--benchmark", default=None,
                        help="Benchmark index name")
    parser.add_argument("--replication", default=None, dest="replication_method",
                        help="Replication method (e.g. Physical, Optimised)")
    parser.add_argument("--no-country", action="store_true",
                        help="Skip yfinance country lookups during holdings upload (faster)")
    args = parser.parse_args()

    db_url = args.db or os.environ.get("DATABASE_PUBLIC_URL")
    if not db_url:
        sys.exit("ERROR: Provide --db or set DATABASE_PUBLIC_URL environment variable.")

    # -- Resolve name / currency --
    print(f"Fetching metadata for {args.ticker} from yfinance ...")
    yf_meta = _fetch_yf_meta(args.ticker)

    name = args.name or yf_meta.get("name") or args.ticker
    currency = args.currency or yf_meta.get("currency") or "USD"

    if not args.name and yf_meta.get("name"):
        print(f"  name:     {name}  (from yfinance)")
    if not args.currency and yf_meta.get("currency"):
        print(f"  currency: {currency}  (from yfinance)")

    # -- Connect to DB --
    engine = create_engine(db_url, echo=False, poolclass=NullPool, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        existing = db.query(ETF).filter(ETF.ticker == args.ticker).first()
        if existing:
            print(f"\nETF '{args.ticker}' already exists (id={existing.id}) - skipping creation.")
            print("  To update metadata edit the DB directly or delete and re-add the ETF.")
        else:
            etf = ETF(
                isin=args.isin.strip().upper(),
                ticker=args.ticker.strip().upper(),
                name=name[:255],
                provider=args.provider,
                domicile=args.domicile.strip().upper(),
                replication_method=args.replication_method,
                ter=Decimal(str(args.ter)) if args.ter is not None else None,
                benchmark=args.benchmark,
                currency=currency[:3].upper(),
            )
            db.add(etf)
            db.commit()
            db.refresh(etf)
            print(f"\nCreated ETF: {etf.name} ({etf.ticker}), id={etf.id}")
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
