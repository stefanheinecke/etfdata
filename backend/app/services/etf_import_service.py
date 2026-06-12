"""
etf_import_service.py — in-process ETF import pipeline for the /admin/import-etf endpoint.

Replicates add_etf.py + upload.py logic without spawning subprocesses or requiring
a database URL from the caller (uses the app's existing SQLAlchemy session).
"""

import io
import os
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from app.schemas import ETF, Performance, Holding, Allocation
from app.services.ishares_import import ISHARES_ETFS, _COUNTRY_ISO, _lookup_country

_EODHD_BASE = "https://eodhd.com/api"


def _eodhd_token() -> str | None:
    return os.getenv("EODHD_TOKEN") or None


def _to_eodhd_symbol(yf_sym: str) -> str:
    """Convert a yfinance-style ticker to EODHD format.
    SWDA.SW  -> SWDA.SW   (SIX, unchanged)
    IVV      -> IVV.US    (US, no suffix)
    SWDA.L   -> SWDA.LSE  (London)
    """
    if "." not in yf_sym:
        return yf_sym + ".US"
    if yf_sym.endswith(".L"):
        return yf_sym[:-2] + ".LSE"
    return yf_sym  # .SW, .AS, etc. unchanged


# ---------------------------------------------------------------------------
# EODHD helpers
# ---------------------------------------------------------------------------

def _fetch_eodhd_meta(eodhd_sym: str, token: str, logs: list) -> dict:
    """Fetch ETF metadata + holdings from EODHD fundamentals endpoint."""
    import requests
    url = f"{_EODHD_BASE}/fundamentals/{eodhd_sym}"
    try:
        resp = requests.get(url, params={"api_token": token}, timeout=20)
        if resp.status_code != 200:
            logs.append(f"  EODHD meta HTTP {resp.status_code} for '{eodhd_sym}'.")
            return {}
        data = resp.json()
        general  = data.get("General", {})
        etf_data = data.get("ETF_Data", {})

        name      = general.get("Name") or general.get("LongName") or ""
        currency  = general.get("CurrencyCode") or general.get("Currency") or ""
        fund_size = etf_data.get("Net_Assets") or etf_data.get("TotalAssets")

        # Holdings: dict keyed by ticker symbol
        raw_holdings = etf_data.get("Holdings") or {}
        holdings = []
        for sym, h in raw_holdings.items():
            weight = h.get("Assets_%")
            if weight is None or float(weight) <= 0:
                continue
            holdings.append({
                "isin":    h.get("Isin") or sym,
                "name":    h.get("Name") or sym,
                "weight":  round(float(weight), 4),
                "sector":  h.get("Sector") or "Equity",
                "country": h.get("Country") or "",
            })

        logs.append(f"  EODHD meta: name='{name}', currency={currency}, "
                    f"fund_size={fund_size}, {len(holdings)} holdings.")
        return {
            "name":      name,
            "currency":  currency,
            "fund_size": int(fund_size) if fund_size else None,
            "holdings":  holdings,
        }
    except Exception as exc:
        logs.append(f"  EODHD meta fetch failed ({exc}).")
        return {}


def _fetch_eodhd_history(eodhd_sym: str, token: str, logs: list):
    """Fetch full price history from EODHD (from 2000-01-01). Returns a DataFrame or None."""
    import requests
    url = f"{_EODHD_BASE}/eod/{eodhd_sym}"
    try:
        resp = requests.get(url, params={
            "api_token": token, "fmt": "json",
            "from": "2000-01-01", "to": date.today().isoformat(), "period": "d"
        }, timeout=60)
        if resp.status_code != 200:
            logs.append(f"  EODHD history HTTP {resp.status_code} for '{eodhd_sym}'.")
            return None
        rows = resp.json()
        if not rows:
            logs.append(f"  EODHD returned empty history for '{eodhd_sym}'.")
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"adjusted_close": "Close", "date": "Date"})
        df = df[["Date", "Close"]].dropna()
        logs.append(f"  EODHD history: {len(df)} rows for '{eodhd_sym}' "
                    f"({df['Date'].min().date()} – {df['Date'].max().date()}).")
        return df
    except Exception as exc:
        logs.append(f"  EODHD history fetch failed ({exc}).")
        return None


# ---------------------------------------------------------------------------
# yfinance helpers (fallback when EODHD_TOKEN not set or EODHD fails)
# ---------------------------------------------------------------------------

def _fetch_yf_meta(yf_symbol: str, logs: list) -> dict:
    import yfinance as yf
    t = yf.Ticker(yf_symbol)
    result: dict = {"ticker_obj": t}  # always present — history() may still work even when info is rate-limited
    try:
        info = t.info or {}
        ter_raw = info.get("totalExpenseRatio")
        ter_pct = round(float(ter_raw) * 100, 4) if ter_raw else None
        fund_size = info.get("totalAssets")
        result.update({
            "name":      info.get("longName") or info.get("shortName") or "",
            "currency":  info.get("currency") or "",
            "ter":       ter_pct,
            "fund_size": int(fund_size) if fund_size else None,
        })
    except Exception as exc:
        logs.append(f"  yfinance metadata lookup failed for '{yf_symbol}' ({exc})")
    return result


def _stooq_symbol(yf_sym: str) -> str:
    """Convert a yfinance symbol to Stooq format (lowercase; US tickers get .us suffix)."""
    sym = yf_sym.lower()
    if "." not in sym:
        sym = sym + ".us"
    return sym


def _fetch_stooq_history(stooq_sym: str, logs: list):
    """Fetch 1-year daily price history from Stooq. Returns a DataFrame or None."""
    import requests, io, pandas as pd
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=366)
    url = "https://stooq.com/q/d/l/"
    params = {"s": stooq_sym, "d1": start.strftime("%Y%m%d"),
              "d2": end.strftime("%Y%m%d"), "i": "d"}
    try:
        resp = requests.get(url, params=params, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or b"No data" in resp.content[:200]:
            logs.append(f"  Stooq returned no data for '{stooq_sym}'.")
            return None
        df = pd.read_csv(io.BytesIO(resp.content))
        # Normalise column names to title-case regardless of what Stooq returns
        df.columns = [c.strip().title() for c in df.columns]
        if "Date" not in df.columns or "Close" not in df.columns:
            logs.append(f"  Stooq CSV has unexpected columns {list(df.columns)} for '{stooq_sym}'.")
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.dropna(subset=["Close"])
        if df.empty:
            logs.append(f"  Stooq returned empty data for '{stooq_sym}'.")
            return None
        logs.append(f"  Stooq fallback succeeded: {len(df)} rows for '{stooq_sym}'.")
        return df
    except Exception as exc:
        logs.append(f"  Stooq fetch failed ({exc}).")
        return None


def _upload_performance(etf: ETF, ticker_obj, currency: str, db, logs: list,
                        perf_yf_symbol: str | None = None) -> int:
    import yfinance as yf

    effective_sym = perf_yf_symbol or etf.ticker
    if perf_yf_symbol:
        logs.append(f"  Using alternate performance ticker: {perf_yf_symbol}")

    ext_df = None       # DataFrame from EODHD
    hist   = None       # yfinance DataFrame
    actual_currency = currency

    token = _eodhd_token()
    if token:
        # --- EODHD (primary when token is configured) ---
        eodhd_sym = _to_eodhd_symbol(effective_sym)
        logs.append(f"  Fetching prices from EODHD ({eodhd_sym})...")
        ext_df = _fetch_eodhd_history(eodhd_sym, token, logs)

    if ext_df is None:
        # --- yfinance fallback ---
        price_ticker = yf.Ticker(perf_yf_symbol) if perf_yf_symbol else ticker_obj
        try:
            hist = price_ticker.history(period="max")
            if hist is not None and not hist.empty:
                try:
                    reported = price_ticker.fast_info.currency or ""
                    if reported:
                        actual_currency = reported
                except Exception:
                    pass
            else:
                hist = None
        except Exception as exc:
            logs.append(f"  yfinance rate-limited ({exc}). No further fallback available.")
            hist = None

    if ext_df is None and (hist is None or hist.empty):
        logs.append("  No price data available.")
        return 0
    gbx_factor = 1.0
    if actual_currency in ("GBp", "GBX", "GBx"):
        gbx_factor = 0.01
        actual_currency = "GBP"
        logs.append("  Prices are in pence (GBX), converting to GBP.")

    db.query(Performance).filter_by(etf_id=etf.id).delete()
    count = 0

    if ext_df is not None:
        # EODHD path
        for _, row in ext_df.iterrows():
            close = float(row["Close"]) * gbx_factor
            if close <= 0:
                continue
            db.add(Performance(
                etf_id=etf.id,
                date=row["Date"].date(),
                close_price=round(close, 4),
                currency=actual_currency[:3].upper(),
            ))
            count += 1
    else:
        # yfinance path
        for idx, row in hist.iterrows():
            close = float(row["Close"]) * gbx_factor
            if close <= 0:
                continue
            div = float(row.get("Dividends", 0) or 0) * gbx_factor
            db.add(Performance(
                etf_id=etf.id,
                date=idx.date(),
                close_price=round(close, 4),
                dividend=round(div, 6) if div else None,
                currency=actual_currency[:3].upper(),
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
    """Full ETF import pipeline (metadata + performance + optional holdings) in-process.

    Args:
        ticker:    ETF ticker (e.g. "SWDA").
        isin:      ETF ISIN (e.g. "IE00B4L5Y983").
        csv_bytes: Raw CSV content bytes, or None to skip holdings import.
        db:        SQLAlchemy session (from get_db()).
        logs:      List to append human-readable log lines to.

    Returns:
        Summary dict with etf_id, ticker, name, and optionally holdings/allocations/skipped.

    Raises:
        ValueError:   Invalid input (bad CSV format).
    """
    ticker = ticker.strip().upper()
    isin   = isin.strip().upper()

    known        = next((e for e in ISHARES_ETFS if e["ticker"] == ticker), None)
    yf_symbol    = (known or {}).get("yf_symbol", ticker)
    perf_sym     = (known or {}).get("perf_yf_symbol")
    known_ter    = (known or {}).get("ter")
    known_bench  = (known or {}).get("benchmark")
    known_url    = (known or {}).get("holdings_url")

    logs.append(f"Using yfinance symbol for metadata: {yf_symbol}")

    # ---- Metadata: EODHD first, yfinance fallback ----
    # For fundamentals use the primary yf_symbol converted to EODHD format
    # (e.g. SWDA.L → SWDA.LSE) — EODHD has fundamentals for LSE/US listings
    # but not always for Swiss (.SW) listings.
    token = _eodhd_token()
    eodhd_meta = {}
    if token:
        eodhd_fund_sym = _to_eodhd_symbol(yf_symbol)   # SWDA.L → SWDA.LSE
        logs.append(f"Fetching metadata from EODHD ({eodhd_fund_sym})...")
        eodhd_meta = _fetch_eodhd_meta(eodhd_fund_sym, token, logs)
        # If LSE listing also 403'd, try the price ticker as last resort
        if not eodhd_meta and perf_sym:
            eodhd_perf_sym = _to_eodhd_symbol(perf_sym)
            logs.append(f"  Retrying fundamentals with {eodhd_perf_sym}...")
            eodhd_meta = _fetch_eodhd_meta(eodhd_perf_sym, token, logs)

    logs.append(f"Fetching metadata from yfinance ({yf_symbol})...")
    yf_meta   = _fetch_yf_meta(yf_symbol, logs)
    name      = name_override or eodhd_meta.get("name") or yf_meta.get("name") or ticker
    # Catalogue currency takes precedence — fundamentals may reflect a different listing's currency
    # (e.g. SWDA.LSE returns GBP but SWDA is USD-denominated and prices come from SWDA.SW)
    currency  = known.get("currency") or eodhd_meta.get("currency") or yf_meta.get("currency") or "USD"
    ter       = ter_override if ter_override is not None else (yf_meta.get("ter") if yf_meta.get("ter") is not None else known_ter)
    fund_size = eodhd_meta.get("fund_size") or yf_meta.get("fund_size")
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
    if ticker_obj is not None or token:
        logs.append("Uploading 1-year performance data...")
        perf_count = _upload_performance(etf, ticker_obj, currency, db, logs,
                                         perf_yf_symbol=perf_sym)
        db.commit()
        logs.append(f"  {perf_count} daily price records inserted.")
    else:
        logs.append("Skipping performance data (yfinance unavailable.)")

    # ---- Holdings: CSV > EODHD > skip ----
    eodhd_holdings = eodhd_meta.get("holdings", [])
    if csv_bytes is not None:
        logs.append("Processing holdings CSV...")
        summary = _process_csv(csv_bytes, etf, db, logs)
        db.commit()
    elif eodhd_holdings:
        logs.append(f"Importing {len(eodhd_holdings)} holdings from EODHD...")
        as_of = date.today()
        db.query(Holding).filter_by(etf_id=etf.id).delete()
        for h in eodhd_holdings:
            db.add(Holding(
                etf_id=etf.id, date=as_of,
                instrument_isin=h["isin"][:12],
                instrument_name=h["name"][:255],
                weight=h["weight"],
                sector=h["sector"],
                country=h["country"],
            ))
        db.commit()
        logs.append(f"  {len(eodhd_holdings)} holdings inserted.")
        summary = {"holdings": len(eodhd_holdings), "skipped": 0}
    else:
        logs.append("No CSV uploaded and no EODHD holdings — holdings import skipped.")
        summary = {}

    return {
        "etf_id": str(etf.id),
        "ticker": etf.ticker,
        "name":   etf.name,
        **summary,
    }
