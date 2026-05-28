"""
etf_import_service.py — in-process ETF import pipeline for the /admin/import-etf endpoint.

Replicates add_etf.py + upload.py logic without spawning subprocesses or requiring
a database URL from the caller (uses the app's existing SQLAlchemy session).
"""

import io
from datetime import date
from decimal import Decimal

import pandas as pd

from app.schemas import ETF, Performance, Holding, Allocation
from app.services.ishares_import import ISHARES_ETFS, _COUNTRY_ISO, _lookup_country


# ---------------------------------------------------------------------------
# yfinance helpers
# ---------------------------------------------------------------------------

def _fetch_yf_meta(yf_symbol: str, logs: list) -> dict:
    try:
        import yfinance as yf
        t = yf.Ticker(yf_symbol)
        info = t.info or {}
        ter_raw = info.get("totalExpenseRatio")
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
        logs.append(f"  yfinance lookup failed for '{yf_symbol}' ({exc})")
        return {}


def _upload_performance(etf: ETF, ticker_obj, currency: str, db, logs: list) -> int:
    hist = ticker_obj.history(period="1y")
    if hist is None or hist.empty:
        logs.append("  No historical price data available from yfinance.")
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
# CSV processing
# ---------------------------------------------------------------------------

def _process_csv(csv_bytes: bytes, etf: ETF, db, logs: list) -> dict:
    """Parse an iShares holdings CSV and upsert holdings + allocations."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df.columns = [c.strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    ticker_col   = col_map.get("ticker")
    name_col     = col_map.get("name")
    weight_col   = col_map.get("weight (%)") or col_map.get("weight(%)")
    isin_col     = col_map.get("isin")
    location_col = col_map.get("location")
    assetcls_col = col_map.get("asset class")
    sector_col   = col_map.get("sector")
    exchange_col = col_map.get("exchange")

    id_col = isin_col if isin_col else ticker_col
    if id_col is None:
        raise ValueError("CSV has no ISIN or Ticker column.")

    missing = [n for n, c in [("Ticker", ticker_col), ("Name", name_col), ("Weight (%)", weight_col)] if c is None]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}. Found: {list(df.columns)}")

    df = df.dropna(subset=[id_col, weight_col])
    df = df[df[id_col].astype(str).str.strip() != ""]

    if assetcls_col:
        mask = df[assetcls_col].astype(str).str.strip().str.lower() == "equity"
        excluded_df = df[~mask].copy()
        df = df[mask]
        logs.append(f"Loaded {len(df)} Equity rows ({len(excluded_df)} non-Equity excluded).")
    else:
        excluded_df = pd.DataFrame()
        logs.append(f"Loaded {len(df)} rows (no Asset Class column — all rows kept).")

    dedup_keys = [id_col, exchange_col] if exchange_col else [id_col]
    before_dedup = len(df)
    agg = {weight_col: "sum"}
    for c in [ticker_col, name_col, location_col, sector_col, assetcls_col]:
        if c and c in df.columns and c not in dedup_keys:
            agg[c] = "first"
    df = df.groupby(dedup_keys, as_index=False).agg(agg)
    dupes = before_dedup - len(df)
    if dupes:
        logs.append(f"Deduplicated {dupes} duplicate row(s) (same ISIN/exchange, weights summed).")

    as_of = date.today()
    deleted_h = db.query(Holding).filter_by(etf_id=etf.id).delete()
    deleted_a = db.query(Allocation).filter_by(etf_id=etf.id).delete()
    if deleted_h:
        logs.append(f"Removed {deleted_h} existing holdings.")
    if deleted_a:
        logs.append(f"Removed {deleted_a} existing allocations.")

    inserted = 0
    skipped = 0
    country_totals: dict[str, float] = {}
    sector_totals:  dict[str, float] = {}

    for _, row in df.iterrows():
        ident  = str(row[id_col]).strip()[:12]
        sym    = str(row[ticker_col]).strip() if ticker_col and pd.notna(row.get(ticker_col, "")) else ident
        name   = str(row[name_col]).strip()[:255] if name_col else ident
        weight = float(row[weight_col])
        if weight <= 0:
            skipped += 1
            continue

        if location_col and pd.notna(row.get(location_col, "")):
            full_name = str(row[location_col]).strip()
            country = _COUNTRY_ISO.get(full_name, "") or _lookup_country(sym)
        else:
            country = _lookup_country(sym)

        sector = "Equity"
        if sector_col and pd.notna(row.get(sector_col, "")):
            sector = str(row[sector_col]).strip() or "Equity"

        db.add(Holding(
            etf_id=etf.id, date=as_of,
            instrument_isin=ident, instrument_name=name,
            weight=float(round(weight, 4)),
            sector=sector, country=country,
        ))
        inserted += 1
        bucket = country if country else "Other"
        country_totals[bucket] = country_totals.get(bucket, 0.0) + weight
        if sector_col and sector:
            sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

    # Cash / non-equity rows → single holding + sector allocation
    cash_weight = 0.0
    if not excluded_df.empty:
        cash_weight = pd.to_numeric(excluded_df[weight_col], errors="coerce").fillna(0).sum()
    if cash_weight > 0:
        db.add(Holding(
            etf_id=etf.id, date=as_of,
            instrument_isin="CASH", instrument_name="Cash & Equivalents",
            weight=float(round(cash_weight, 4)),
            sector="Cash", country="",
        ))
        inserted += 1
        sector_totals["Cash"]  = sector_totals.get("Cash", 0.0) + cash_weight
        country_totals["Cash"] = country_totals.get("Cash", 0.0) + cash_weight

    # Normalize to 100%
    ct = sum(country_totals.values())
    st = sum(sector_totals.values())
    if ct > 0:
        country_totals = {k: v / ct * 100 for k, v in country_totals.items()}
    if st > 0:
        sector_totals  = {k: v / st  * 100 for k, v in sector_totals.items()}

    alloc_count = 0
    for bucket, w in country_totals.items():
        db.add(Allocation(etf_id=etf.id, date=as_of, type="country", bucket=bucket, weight=float(round(w, 4))))
        alloc_count += 1
    for bucket, w in sector_totals.items():
        db.add(Allocation(etf_id=etf.id, date=as_of, type="sector", bucket=bucket, weight=float(round(w, 4))))
        alloc_count += 1

    logs.append(f"Inserted {inserted} holdings, {alloc_count} allocations. Skipped {skipped} (zero weight).")
    return {"holdings": inserted, "allocations": alloc_count, "skipped": skipped}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def import_etf(
    ticker: str,
    isin: str,
    csv_bytes: bytes | None,
    db,
    logs: list,
    name_override: str | None = None,
    ter_override: float | None = None,
) -> dict:
    """
    Full ETF import pipeline (metadata + performance + holdings) in-process.

    Args:
        ticker:    ETF ticker (e.g. "SWDA").
        isin:      ETF ISIN (e.g. "IE00B4L5Y983").
        csv_bytes: Raw CSV content bytes, or None to auto-download.
        db:        SQLAlchemy session (from get_db()).
        logs:      List to append human-readable log lines to.

    Returns:
        Summary dict with etf_id, ticker, name, holdings, allocations, skipped.

    Raises:
        ValueError:   Invalid input (bad CSV, ticker not in built-in list with no CSV).
        RuntimeError: Network / download failure.
    """
    ticker = ticker.strip().upper()
    isin   = isin.strip().upper()

    known        = next((e for e in ISHARES_ETFS if e["ticker"] == ticker), None)
    yf_symbol    = (known or {}).get("yf_symbol", ticker)
    known_ter    = (known or {}).get("ter")
    known_bench  = (known or {}).get("benchmark")
    known_url    = (known or {}).get("holdings_url")

    logs.append(f"Using yfinance symbol: {yf_symbol}")

    # ---- Auto-download CSV if not uploaded ----
    if csv_bytes is None:
        if not known_url:
            raise ValueError(
                f"No CSV uploaded and no built-in holdings URL for '{ticker}'. "
                "Upload a CSV file or add the ticker to the ISHARES_ETFS built-in list."
            )
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
        logs.append("Downloading holdings CSV from iShares...")
        try:
            resp = requests.get(known_url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Network error downloading CSV: {exc}")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} downloading holdings CSV.")
        preview = resp.content[:200].decode("utf-8", errors="ignore").lstrip()
        if "html" in resp.headers.get("Content-Type", "").lower() or preview.lower().startswith("<!doctype"):
            raise RuntimeError(
                "iShares returned an HTML page instead of CSV (cookie/bot wall). "
                "Download the file manually and upload it here."
            )
        csv_bytes = resp.content
        logs.append(f"Downloaded {len(csv_bytes):,} bytes.")

    # ---- yfinance metadata ----
    logs.append(f"Fetching metadata from yfinance ({yf_symbol})...")
    yf_meta   = _fetch_yf_meta(yf_symbol, logs)
    name      = name_override or yf_meta.get("name") or ticker
    currency  = yf_meta.get("currency") or "USD"
    ter       = ter_override if ter_override is not None else (yf_meta.get("ter") if yf_meta.get("ter") is not None else known_ter)
    fund_size = yf_meta.get("fund_size")
    benchmark = known_bench
    logs.append(f"  name={name}, currency={currency}, ter={ter}%, benchmark={benchmark}")

    # ---- Upsert ETF row ----
    etf = db.query(ETF).filter(ETF.ticker == ticker).first()
    if etf:
        etf.name = name[:255]
        if ter is not None:
            etf.ter = Decimal(str(ter))
        if fund_size is not None:
            etf.fund_size = fund_size
        if benchmark:
            etf.benchmark = benchmark
        if currency:
            etf.currency = currency[:3].upper()
        db.commit()
        db.refresh(etf)
        logs.append(f"Updated existing ETF: {etf.name} ({etf.ticker}), id={etf.id}")
    else:
        etf = ETF(
            isin=isin, ticker=ticker,
            name=name[:255], provider="iShares",
            domicile="IE", replication_method="Physical",
            ter=Decimal(str(ter)) if ter is not None else None,
            fund_size=fund_size, benchmark=benchmark,
            currency=currency[:3].upper(),
        )
        db.add(etf)
        db.commit()
        db.refresh(etf)
        logs.append(f"Created new ETF: {etf.name} ({etf.ticker}), id={etf.id}")

    # ---- Performance ----
    ticker_obj = yf_meta.get("ticker_obj")
    if ticker_obj is not None:
        logs.append("Uploading 1-year performance data...")
        perf_count = _upload_performance(etf, ticker_obj, currency, db, logs)
        db.commit()
        logs.append(f"  {perf_count} daily price records inserted.")
    else:
        logs.append("Skipping performance data (yfinance unavailable).")

    # ---- Holdings ----
    logs.append("Processing holdings CSV...")
    summary = _process_csv(csv_bytes, etf, db, logs)
    db.commit()

    return {
        "etf_id": str(etf.id),
        "ticker": etf.ticker,
        "name":   etf.name,
        **summary,
    }
