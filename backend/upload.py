"""
upload.py — upload a holdings CSV to the PostgreSQL database.

Usage (Railway DATABASE_URL in env):
    set DATABASE_URL=postgresql://user:pass@host:5432/railway
    python upload.py --csv "C:/Downloads/SEDY_holdings.csv" --ticker IEDY

Or pass the URL directly:
    python upload.py --csv ... --ticker IEDY --db "postgresql://..."

The CSV must contain at least these columns (iShares download format):
    Ticker, Name, Weight (%)
"""

import argparse
import os
import sys
import time
from datetime import date

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Resolve the app package relative to this file so imports work when run
# directly (i.e. without installing the package).
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from app.schemas import ETF, Holding, Allocation

# ---------------------------------------------------------------------------
# Country lookup (same mapping as ishares_import.py)
# ---------------------------------------------------------------------------
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
_country_cache: dict[str, str] = {}


def _lookup_country(symbol: str) -> str:
    if symbol in _country_cache:
        return _country_cache[symbol]
    try:
        import yfinance as yf
        full_name = yf.Ticker(symbol).info.get("country", "") or ""
        code = _COUNTRY_ISO.get(full_name, "")
        time.sleep(0.3)
    except Exception:
        code = ""
    _country_cache[symbol] = code
    return code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload ETF holdings CSV to PostgreSQL")
    parser.add_argument("--csv", required=True, help="Path to the holdings CSV file")
    parser.add_argument("--ticker", required=True, help="ETF ticker symbol as stored in the DB (e.g. IEDY)")
    parser.add_argument("--db", default=None, help="DATABASE_URL (overrides DATABASE_URL env var)")
    parser.add_argument("--no-country", action="store_true", help="Skip yfinance country lookups (faster)")
    args = parser.parse_args()

    db_url = args.db or os.environ.get("DATABASE_PUBLIC_URL")
    if not db_url:
        sys.exit("ERROR: Provide DATABASE_URL via --db or the DATABASE_URL environment variable.")

    # -- Load CSV --
    df = pd.read_csv(args.csv)

    # Normalise column names: strip whitespace, lowercase for matching
    df.columns = [c.strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    ticker_col    = col_map.get("ticker")
    name_col      = col_map.get("name")
    weight_col    = col_map.get("weight (%)") or col_map.get("weight(%)")
    location_col  = col_map.get("location")    # iShares CSVs include full country name here
    assetcls_col  = col_map.get("asset class")
    sector_col    = col_map.get("sector")

    missing = [n for n, c in [("Ticker", ticker_col), ("Name", name_col), ("Weight (%)", weight_col)] if c is None]
    if missing:
        sys.exit(f"ERROR: CSV is missing required columns: {missing}\nFound: {list(df.columns)}")

    # Drop rows without a ticker or weight
    df = df.dropna(subset=[ticker_col, weight_col])
    df = df[df[ticker_col].astype(str).str.strip() != ""]

    # Filter to Equity rows only; keep excluded rows for the summary report
    if assetcls_col:
        mask = df[assetcls_col].astype(str).str.strip().str.lower() == "equity"
        excluded_df = df[~mask].copy()
        df = df[mask]
        print(f"Loaded {len(df)} Equity rows from {args.csv} ({len(excluded_df)} non-Equity rows excluded)")
    else:
        excluded_df = pd.DataFrame()
        print(f"Loaded {len(df)} rows from {args.csv} (no 'Asset Class' column found — all rows kept)")
    if location_col:
        print(f"Location column '{location_col}' found — ISO2 codes read from CSV (fast)")
    else:
        print("No Location column found — ISO2 codes looked up via yfinance (slower)")

    # -- Connect to DB --
    engine = create_engine(db_url, echo=False, poolclass=NullPool, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        etf = db.query(ETF).filter(ETF.ticker == args.ticker).first()
        if etf is None:
            sys.exit(f"ERROR: No ETF with ticker '{args.ticker}' found in the database.")
        print(f"Found ETF: {etf.name} (id={etf.id})")

        as_of = date.today()

        # Delete all existing holdings and allocations for this ETF regardless of date,
        # so stale rows are fully replaced.
        deleted_h = db.query(Holding).filter_by(etf_id=etf.id).delete()
        deleted_a = db.query(Allocation).filter_by(etf_id=etf.id).delete()
        if deleted_h:
            print(f"Removed {deleted_h} existing holdings for {etf.ticker}")
        if deleted_a:
            print(f"Removed {deleted_a} existing allocations for {etf.ticker}")

        inserted = 0
        skipped = 0
        country_totals: dict[str, float] = {}
        sector_totals: dict[str, float] = {}
        unmapped_locations: dict[str, float] = {}  # full name -> weight sum for unmapped countries

        for _, row in df.iterrows():
            sym    = str(row[ticker_col]).strip()[:12]
            name   = str(row[name_col]).strip()[:255] if name_col else sym
            weight = float(row[weight_col])
            if weight <= 0:
                skipped += 1
                continue

            # Prefer the Location column (full name → ISO2) over a yfinance network call
            if args.no_country:
                country = ""
            elif location_col and pd.notna(row[location_col]):
                full_name = str(row[location_col]).strip()
                country = _COUNTRY_ISO.get(full_name, "")
                if not country:
                    country = _lookup_country(sym)
                if not country and full_name:
                    unmapped_locations[full_name] = unmapped_locations.get(full_name, 0.0) + weight
            else:
                country = _lookup_country(sym)

            # Sector from CSV column
            sector = "Equity"
            if sector_col and pd.notna(row[sector_col]):
                sector = str(row[sector_col]).strip() or "Equity"

            db.add(Holding(
                etf_id=etf.id,
                date=as_of,
                instrument_isin=sym,
                instrument_name=name,
                weight=round(weight, 4),
                sector=sector,
                country=country,
            ))
            inserted += 1
            print(f"  {sym:12s}  {weight:7.4f}%  {country or '??':4s}  {sector}")

            # Accumulate allocation totals
            bucket = country if country else "Other"
            country_totals[bucket] = country_totals.get(bucket, 0.0) + weight
            if sector_col and sector:
                sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

        # -- Cash allocation from excluded non-equity rows --
        # Non-equity rows (cash, futures, etc.) are excluded from allocations entirely.
        # Normalize remaining equity weights to sum to 100%.
        country_total_raw = sum(country_totals.values())
        sector_total_raw  = sum(sector_totals.values())
        if country_total_raw > 0:
            country_totals = {k: v / country_total_raw * 100 for k, v in country_totals.items()}
        if sector_total_raw > 0:
            sector_totals  = {k: v / sector_total_raw  * 100 for k, v in sector_totals.items()}

        # -- Allocations --
        alloc_count = 0
        for country, weight in country_totals.items():
            db.add(Allocation(
                etf_id=etf.id, date=as_of,
                type="country", bucket=country,
                weight=round(weight, 4),
            ))
            alloc_count += 1
        for sector, weight in sector_totals.items():
            db.add(Allocation(
                etf_id=etf.id, date=as_of,
                type="sector", bucket=sector,
                weight=round(weight, 4),
            ))
            alloc_count += 1

        db.commit()

        total_country_pct = sum(country_totals.values())
        total_sector_pct  = sum(sector_totals.values())

        print(f"\nDone — inserted {inserted} holdings, {alloc_count} allocations, skipped {skipped} (weight ≤ 0).")

        # Country summary
        print(f"\n── Country allocations ({total_country_pct:.2f}% total) ──")
        for c, w in sorted(country_totals.items(), key=lambda x: -x[1]):
            flag = " ← UNKNOWN" if c == "Other" else ""
            print(f"  {c:4s}  {w:7.4f}%{flag}")
        if unmapped_locations:
            print(f"\n  Unmapped location names bucketed as 'Other' (add to _COUNTRY_ISO to fix):")
            for loc, w in sorted(unmapped_locations.items(), key=lambda x: -x[1]):
                print(f"    {w:7.4f}%  '{loc}'")

        # Sector summary
        if sector_totals:
            print(f"\n── Sector allocations ({total_sector_pct:.2f}% total) ──")
            for s, w in sorted(sector_totals.items(), key=lambda x: -x[1]):
                print(f"  {w:7.4f}%  {s}")
        elif not sector_col:
            print("\n── Sector allocations: no 'Sector' column found in CSV ──")

        # Excluded (non-Equity) rows — now counted as Cash & Equivalents
        if not excluded_df.empty:
            excl_weight = pd.to_numeric(excluded_df[weight_col], errors='coerce').fillna(0)
            excl_total  = excl_weight.sum()
            print(f"\n── Non-Equity rows ({excl_total:.4f}%) counted as Cash & Equivalents ──")
            for _, row in excluded_df.iterrows():
                sym  = str(row[ticker_col]).strip()[:12]
                name = str(row[name_col]).strip()[:50] if name_col else ""
                cls  = str(row[assetcls_col]).strip() if assetcls_col else "?"
                w    = pd.to_numeric(row[weight_col], errors='coerce') or 0.0
                print(f"  {sym:12s}  {w:7.4f}%  [{cls}]  {name}")

    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
