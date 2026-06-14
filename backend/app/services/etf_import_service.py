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
from app.services.ishares_import import _COUNTRY_ISO, _lookup_country

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
        general  = data.get("General") or {}
        etf_data = data.get("ETF_Data") or {}  # EODHD sends null for European ETFs — treat as {}

        name      = general.get("Name") or general.get("LongName") or ""
        if not name:
            # EODHD returned a response but with no ETF data — symbol not in their database
            # or the exchange code is wrong. Returning {} lets the caller try a fallback.
            logs.append(f"  EODHD: empty fundamentals for '{eodhd_sym}' "
                        f"(keys: {list(data.keys())}, body: {resp.text[:300]!r}).")
            return {}
        currency  = general.get("CurrencyCode") or general.get("Currency") or ""
        fund_size = (etf_data.get("Net_Assets") or etf_data.get("NetAssets") or
                     etf_data.get("TotalNetAssets") or etf_data.get("TotalAssets"))
        # ISIN: EODHD puts it in ETF_Data, not in General
        isin      = (etf_data.get("ISIN") or etf_data.get("Isin") or
                     general.get("ISIN") or general.get("Isin") or
                     general.get("isin") or "").strip()

        # Log which keys actually have values — helps diagnose field-name mismatches
        non_empty_general = [k for k, v in general.items() if v not in (None, "", {}, [])]
        non_empty_keys    = [k for k, v in etf_data.items() if v not in (None, "", {}, [])]
        logs.append(f"  EODHD General non-empty keys: {non_empty_general[:30]}")
        logs.append(f"  EODHD ETF_Data non-empty keys: {non_empty_keys[:25]}")

        # Provider / fund family
        provider = (general.get("Fund_Family") or general.get("FundFamily") or
                    etf_data.get("Company_Name") or "iShares").strip() or "iShares"

        # Domicile: ETF_Data.Domicile has the fund's legal domicile (e.g. "Ireland").
        # General.CountryISO is the exchange country (e.g. "CH" for SIX) — not the fund domicile.
        domicile_raw = etf_data.get("Domicile") or ""
        if domicile_raw:
            # Full country name → ISO-2 via the shared map ("Ireland" → "IE", etc.)
            domicile = _COUNTRY_ISO.get(domicile_raw, domicile_raw[:2].upper())
        else:
            fallback = (general.get("CountryISO") or general.get("CountryCode") or "IE").strip()
            domicile = fallback[:2].upper() if fallback else "IE"

        # TER:
        # - TotalExpenseRatio / Expense_Ratio / OngoingCharge / ManagementFee are decimal
        #   fractions (0.0018 = 0.18%) — multiply by 100 if value < 1.
        # - Ongoing_Charge (with underscore) is already in percent (0.1000 = 0.10%) — use as-is.
        ter_pct = None
        ter_raw = (etf_data.get("TotalExpenseRatio") or etf_data.get("Expense_Ratio") or
                   etf_data.get("OngoingCharge") or etf_data.get("ManagementFee") or
                   general.get("TotalExpenseRatio"))
        if ter_raw is not None:
            try:
                f = float(ter_raw)
                ter_pct = round(f * 100, 4) if f < 1 else round(f, 4)
            except (ValueError, TypeError):
                pass
        if ter_pct is None:
            ongoing = etf_data.get("Ongoing_Charge")
            if ongoing is not None:
                try:
                    ter_pct = round(float(ongoing), 4)
                except (ValueError, TypeError):
                    pass

        # Benchmark index
        benchmark = (
            etf_data.get("BenchmarkName") or
            etf_data.get("Index_Name") or
            etf_data.get("IndexName") or
            None
        )

        # Dividend policy from EODHD or inferred from fund name
        div_policy = None
        etf_type = (etf_data.get("Type") or etf_data.get("InvestmentType") or "").lower()
        if "accum" in etf_type or "(acc)" in name.lower():
            div_policy = "Accumulating"
        elif "distrib" in etf_type or "(dist)" in name.lower():
            div_policy = "Distributing"

        # Holdings: dict keyed by ticker symbol
        raw_holdings = etf_data.get("Holdings") or {}
        holdings = []
        for sym, h in raw_holdings.items():
            weight = h.get("Assets_%")
            if weight is None or float(weight) <= 0:
                continue
            raw_country = (h.get("Country") or "").strip()
            holdings.append({
                "isin":    h.get("Isin") or sym,
                "name":    h.get("Name") or sym,
                "weight":  round(float(weight), 4),
                "sector":  h.get("Sector") or "Equity",
                "country": _COUNTRY_ISO.get(raw_country, ""),
            })

        logs.append(f"  EODHD meta: name='{name}', isin={isin}, currency={currency}, "
                    f"ter={ter_pct}%, benchmark='{benchmark}', domicile={domicile}, "
                    f"provider={provider}, fund_size={fund_size}, div_policy={div_policy}, "
                    f"{len(holdings)} holdings.")
        return {
            "name":            name,
            "currency":        currency,
            "fund_size":       int(fund_size) if fund_size else None,
            "isin":            isin,
            "ter":             ter_pct,
            "benchmark":       benchmark,
            "domicile":        domicile,
            "provider":        provider,
            "holdings":        holdings,
            "dividend_policy": div_policy,
        }
    except Exception as exc:
        logs.append(f"  EODHD meta fetch failed ({exc}).")
        return {}


def _fetch_eodhd_isin(eodhd_sym: str, token: str, logs: list) -> str:
    """Look up ISIN for an ETF via EODHD search API (always returns ISIN in results)."""
    import requests
    try:
        resp = requests.get(f"{_EODHD_BASE}/search/{eodhd_sym}",
                            params={"api_token": token, "limit": 5}, timeout=10)
        if resp.status_code != 200:
            return ""
        results = resp.json()
        code = eodhd_sym.split(".")[0].upper()
        for r in results:
            if r.get("Code", "").upper() == code and r.get("ISIN"):
                logs.append(f"  EODHD search: found ISIN={r['ISIN']} for {eodhd_sym}")
                return r["ISIN"]
        # Try any result with an ISIN
        for r in results:
            if r.get("ISIN"):
                logs.append(f"  EODHD search fallback: ISIN={r['ISIN']} from first match")
                return r["ISIN"]
    except Exception as exc:
        logs.append(f"  EODHD ISIN search failed ({exc}).")
    return ""


def _fetch_eodhd_currency(eodhd_sym: str, token: str, logs: list) -> str | None:
    """Detect the trading currency of an EODHD listing via the search API."""
    import requests
    try:
        resp = requests.get(f"{_EODHD_BASE}/search/{eodhd_sym}",
                            params={"api_token": token, "limit": 5}, timeout=10)
        if resp.status_code != 200:
            return None
        results = resp.json()
        # Match the exact code
        code = eodhd_sym.split(".")[0].upper()
        for r in results:
            if r.get("Code", "").upper() == code:
                return r.get("Currency") or r.get("currency")
        # Fall back to first result's currency
        if results:
            return results[0].get("Currency") or results[0].get("currency")
    except Exception as exc:
        logs.append(f"  EODHD currency lookup failed ({exc}).")
    return None


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


def _upload_performance(etf: ETF, eodhd_symbol: str, currency: str, db, logs: list) -> int:
    """Fetch price history from EODHD and insert Performance rows."""
    token = _eodhd_token()
    if not token:
        logs.append("  Skipping performance (EODHD_TOKEN not set).")
        return 0

    actual_currency = currency
    ext_df = _fetch_eodhd_history(eodhd_symbol, token, logs)
    if ext_df is None:
        logs.append("  No price data available from EODHD.")
        return 0

    # Detect the actual trading currency for this listing
    detected = _fetch_eodhd_currency(eodhd_symbol, token, logs)
    if detected:
        actual_currency = detected
        logs.append(f"  Price currency for {eodhd_symbol}: {actual_currency}")

    gbx_factor = 1.0
    if actual_currency in ("GBp", "GBX", "GBx"):
        gbx_factor = 0.01
        actual_currency = "GBP"
        logs.append("  Prices are in pence (GBX), converting to GBP.")

    db.query(Performance).filter_by(etf_id=etf.id).delete()
    count = 0
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
    eodhd_symbol: str,
    csv_bytes: bytes | None,
    db,
    logs: list,
    isin_override: str | None = None,
    name_override: str | None = None,
    ter_override: float | None = None,
) -> dict:
    """Full ETF import pipeline driven by an EODHD symbol (e.g. 'EIMI.SW', 'SWDA.LSE').

    All metadata (name, ISIN, TER, benchmark, domicile, provider, holdings) is fetched
    from EODHD.  Price history uses the same symbol so the currency reflects the chosen
    listing (e.g. USD for .SW listings, GBP for .LSE listings).

    If EODHD fundamentals are unavailable for the given exchange (common for .SW listings),
    the LSE equivalent is tried automatically as a fallback.

    Args:
        eodhd_symbol: EODHD-format symbol, e.g. 'EIMI.SW' or 'SWDA.LSE'.
        csv_bytes:    Optional holdings CSV bytes; takes precedence over EODHD holdings.
        db:           SQLAlchemy session.
        logs:         List to append human-readable log lines to.
        isin_override: Override ISIN if EODHD does not return one.
        name_override: Override the ETF name.
        ter_override:  Override the TER (%).

    Returns:
        Summary dict with etf_id, ticker, name, and optionally holdings/skipped counts.

    Raises:
        ValueError: ISIN could not be resolved.
    """
    eodhd_symbol = eodhd_symbol.strip().upper()
    ticker = eodhd_symbol.split(".")[0]

    logs.append(f"Importing ETF from EODHD symbol: {eodhd_symbol}")

    # ---- Metadata: EODHD ----
    token = _eodhd_token()
    eodhd_meta: dict = {}
    if token:
        logs.append(f"Fetching metadata from EODHD ({eodhd_symbol})...")
        eodhd_meta = _fetch_eodhd_meta(eodhd_symbol, token, logs)
        # EODHD fundamentals are often absent for non-US exchange listings.
        # Try a prioritised list of exchange fallbacks that carry richer ETF data.
        if not eodhd_meta or not eodhd_meta.get("name"):
            # Exchanges tried in order; stop at the first that returns a name.
            eodhd_orig_exchange = eodhd_symbol.split(".")[-1] if "." in eodhd_symbol else ""
            fallback_exchanges = [e for e in ["LSE", "XETRA", "MI", "PA", "AS"]
                                  if e != eodhd_orig_exchange]
            for fb_exch in fallback_exchanges:
                fb_sym = f"{ticker}.{fb_exch}"
                logs.append(f"  No fundamentals for {eodhd_symbol}, retrying with {fb_sym}...")
                eodhd_meta = _fetch_eodhd_meta(fb_sym, token, logs)
                if eodhd_meta and eodhd_meta.get("name"):
                    break
        elif not eodhd_meta.get("isin"):
            # Got partial data but no ISIN — supplement missing fields from the LSE listing.
            # Currency is intentionally kept from the original symbol (e.g. USD for .SW).
            lse_sym = f"{ticker}.LSE"
            if lse_sym != eodhd_symbol:
                logs.append(f"  ISIN missing from {eodhd_symbol}, supplementing from {lse_sym}...")
                lse_meta = _fetch_eodhd_meta(lse_sym, token, logs)
                if lse_meta:
                    orig_currency = eodhd_meta.get("currency")
                    for field in ["isin", "benchmark", "ter", "domicile", "provider",
                                  "dividend_policy", "holdings"]:
                        if not eodhd_meta.get(field) and lse_meta.get(field):
                            eodhd_meta[field] = lse_meta[field]
                    # Restore original currency — LSE returns GBP but e.g. .SW trades in USD
                    if orig_currency:
                        eodhd_meta["currency"] = orig_currency
    else:
        logs.append("  Warning: EODHD_TOKEN not configured — cannot fetch metadata or prices.")

    if not eodhd_meta or not eodhd_meta.get("name"):
        logs.append(f"  All EODHD exchange variants returned no data for '{eodhd_symbol}'. "
                    f"ETF created with minimal metadata.")

    # If EODHD gave us a name but is still missing ISIN, try the EODHD search API
    if eodhd_meta.get("name") and not eodhd_meta.get("isin") and token:
        found_isin = _fetch_eodhd_isin(eodhd_symbol, token, logs)
        if not found_isin:
            found_isin = _fetch_eodhd_isin(f"{ticker}.LSE", token, logs)
        if found_isin:
            eodhd_meta["isin"] = found_isin

    isin = (isin_override or eodhd_meta.get("isin") or "").strip().upper() or None
    if not isin:
        logs.append(f"  Warning: ISIN not found for '{eodhd_symbol}' — proceeding without it.")

    name      = name_override or eodhd_meta.get("name") or ticker
    currency  = eodhd_meta.get("currency") or "USD"
    ter       = ter_override if ter_override is not None else eodhd_meta.get("ter")
    fund_size = eodhd_meta.get("fund_size")
    benchmark = eodhd_meta.get("benchmark")
    domicile  = eodhd_meta.get("domicile") or "IE"
    provider  = eodhd_meta.get("provider") or "iShares"
    div_policy = eodhd_meta.get("dividend_policy")
    if not div_policy:
        n = name.lower()
        if "(acc)" in n or "accumul" in n:
            div_policy = "Accumulating"
        elif "(dist)" in n or "distribut" in n:
            div_policy = "Distributing"
    logs.append(f"  name={name}, currency={currency}, ter={ter}%, isin={isin}, "
                f"domicile={domicile}, provider={provider}, dividend_policy={div_policy}")

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
        if div_policy:
            etf.dividend_policy = div_policy
        etf.provider = provider
        etf.domicile = domicile
        db.commit()
        db.refresh(etf)
        logs.append(f"Updated existing ETF: {etf.name} ({etf.ticker}), id={etf.id}")
    else:
        etf = ETF(
            isin=isin, ticker=ticker,
            name=name[:255], provider=provider,
            domicile=domicile, replication_method="Physical",
            ter=Decimal(str(ter)) if ter is not None else None,
            fund_size=fund_size, benchmark=benchmark,
            currency=currency[:3].upper(),
            dividend_policy=div_policy,
        )
        db.add(etf)
        db.commit()
        db.refresh(etf)
        logs.append(f"Created new ETF: {etf.name} ({etf.ticker}), id={etf.id}")

    # ---- Performance ----
    logs.append("Uploading performance data...")
    perf_count = _upload_performance(etf, eodhd_symbol, currency, db, logs)
    db.commit()
    logs.append(f"  {perf_count} daily price records inserted.")

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
        db.query(Allocation).filter_by(etf_id=etf.id).delete()
        country_totals: dict[str, float] = {}
        sector_totals:  dict[str, float] = {}
        for h in eodhd_holdings:
            db.add(Holding(
                etf_id=etf.id, date=as_of,
                instrument_isin=h["isin"][:12],
                instrument_name=h["name"][:255],
                weight=h["weight"],
                sector=h["sector"],
                country=h["country"],
            ))
            if h["country"]:
                country_totals[h["country"]] = country_totals.get(h["country"], 0.0) + h["weight"]
            if h["sector"]:
                sector_totals[h["sector"]] = sector_totals.get(h["sector"], 0.0) + h["weight"]

        # Normalise to 100% and insert allocations
        ct = sum(country_totals.values())
        st = sum(sector_totals.values())
        if ct > 0:
            country_totals = {k: v / ct * 100 for k, v in country_totals.items()}
        if st > 0:
            sector_totals  = {k: v / st * 100 for k, v in sector_totals.items()}
        alloc_count = 0
        for bucket, w in country_totals.items():
            db.add(Allocation(etf_id=etf.id, date=as_of, type="country",
                              bucket=bucket, weight=round(w, 4)))
            alloc_count += 1
        for bucket, w in sector_totals.items():
            db.add(Allocation(etf_id=etf.id, date=as_of, type="sector",
                              bucket=bucket, weight=round(w, 4)))
            alloc_count += 1

        db.commit()
        logs.append(f"  {len(eodhd_holdings)} holdings and {alloc_count} allocations inserted.")
        summary = {"holdings": len(eodhd_holdings), "allocations": alloc_count, "skipped": 0}
    else:
        logs.append("No CSV uploaded and no EODHD holdings — holdings import skipped.")
        summary = {}

    return {
        "etf_id": str(etf.id),
        "ticker": etf.ticker,
        "name":   etf.name,
        **summary,
    }
