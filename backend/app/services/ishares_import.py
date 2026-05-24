"""
iShares ETF holdings importer.

Downloads CSV holdings files directly from iShares public download URLs,
parses them and upserts into the database.
"""

import csv
import io
import logging
from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from app.schemas import ETF, Holding, Allocation

logger = logging.getLogger(__name__)

# ── HTTP headers that mimic a real browser ────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.ishares.com/us/",
}

# ── 10 iShares ETFs to import ─────────────────────────────────────────────────
# product_id comes from the iShares product URL; isin from public fund pages.
ISHARES_ETFS = [
    {
        "product_id": "239726",
        "slug": "ishares-core-sp-500-etf",
        "ticker": "IVV",
        "name": "iShares Core S&P 500 ETF",
        "isin": "US4642872000",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.03,
        "replication_method": "Physical",
        "benchmark": "S&P 500 Index",
    },
    {
        "product_id": "239714",
        "slug": "ishares-russell-2000-etf",
        "ticker": "IWM",
        "name": "iShares Russell 2000 ETF",
        "isin": "US4642876555",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.19,
        "replication_method": "Physical",
        "benchmark": "Russell 2000 Index",
    },
    {
        "product_id": "239724",
        "slug": "ishares-russell-1000-growth-etf",
        "ticker": "IWF",
        "name": "iShares Russell 1000 Growth ETF",
        "isin": "US4642876308",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.19,
        "replication_method": "Physical",
        "benchmark": "Russell 1000 Growth Index",
    },
    {
        "product_id": "239713",
        "slug": "ishares-russell-1000-value-etf",
        "ticker": "IWD",
        "name": "iShares Russell 1000 Value ETF",
        "isin": "US4642876316",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.19,
        "replication_method": "Physical",
        "benchmark": "Russell 1000 Value Index",
    },
    {
        "product_id": "239763",
        "slug": "ishares-core-sp-mid-cap-etf",
        "ticker": "IJH",
        "name": "iShares Core S&P Mid-Cap ETF",
        "isin": "US4642874329",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.05,
        "replication_method": "Physical",
        "benchmark": "S&P MidCap 400 Index",
    },
    {
        "product_id": "239770",
        "slug": "ishares-core-sp-small-cap-etf",
        "ticker": "IJR",
        "name": "iShares Core S&P Small-Cap ETF",
        "isin": "US46428V7X74",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.06,
        "replication_method": "Physical",
        "benchmark": "S&P SmallCap 600 Index",
    },
    {
        "product_id": "239623",
        "slug": "ishares-msci-eafe-etf",
        "ticker": "EFA",
        "name": "iShares MSCI EAFE ETF",
        "isin": "US4642874659",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.32,
        "replication_method": "Physical",
        "benchmark": "MSCI EAFE Index",
    },
    {
        "product_id": "239637",
        "slug": "ishares-msci-emerging-markets-etf",
        "ticker": "EEM",
        "name": "iShares MSCI Emerging Markets ETF",
        "isin": "US4642864657",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.68,
        "replication_method": "Physical",
        "benchmark": "MSCI Emerging Markets Index",
    },
    {
        "product_id": "239458",
        "slug": "ishares-core-total-us-bond-market-etf",
        "ticker": "AGG",
        "name": "iShares Core U.S. Aggregate Bond ETF",
        "isin": "US4642872422",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.03,
        "replication_method": "Physical",
        "benchmark": "Bloomberg U.S. Aggregate Bond Index",
    },
    {
        "product_id": "239566",
        "slug": "ishares-iboxx-investment-grade-corporate-bond-etf",
        "ticker": "LQD",
        "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "isin": "US4642881041",
        "currency": "USD",
        "domicile": "US",
        "ter": 0.14,
        "replication_method": "Physical",
        "benchmark": "Markit iBoxx USD Liquid Investment Grade Index",
    },
    # ── European UCITS ETFs (iShares DE site) ────────────────────────────────
    {
        "product_id": "251882",
        "slug": "ishares-msci-world-ucits-etf-acc-fund",
        "ticker": "SWDA",
        "name": "iShares Core MSCI World UCITS ETF USD (Acc)",
        "isin": "IE00B4L5Y983",
        "currency": "USD",
        "domicile": "IE",
        "ter": 0.20,
        "replication_method": "Physical",
        "benchmark": "MSCI World Index",
        "site": "eu",
    },
    {
        "product_id": "253743",
        "slug": "ishares-sp-500-b-ucits-etf-acc-fund",
        "ticker": "CSSPX",
        "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",
        "isin": "IE00B5BMR087",
        "currency": "USD",
        "domicile": "IE",
        "ter": 0.07,
        "replication_method": "Physical",
        "benchmark": "S&P 500 Index",
        "site": "eu",
    },
    {
        "product_id": "251766",
        "slug": "ishares-emerging-markets-dividend-ucits-etf",
        "ticker": "IEDY",
        "name": "iShares Emerging Markets Dividend UCITS ETF",
        "isin": "IE00B652H904",
        "currency": "USD",
        "domicile": "IE",
        "ter": 0.65,
        "replication_method": "Physical",
        "benchmark": "Dow Jones Emerging Markets Select Dividend Index",
        "site": "eu",
    },
]

# ── Location name → ISO 3166-1 alpha-2 ───────────────────────────────────────
_COUNTRY_MAP = {
    "United States": "US",
    "Japan": "JP",
    "United Kingdom": "GB",
    "France": "FR",
    "Germany": "DE",
    "Canada": "CA",
    "Switzerland": "CH",
    "Australia": "AU",
    "Netherlands": "NL",
    "Denmark": "DK",
    "Sweden": "SE",
    "Spain": "ES",
    "Italy": "IT",
    "Hong Kong": "HK",
    "Singapore": "SG",
    "South Korea": "KR",
    "Taiwan": "TW",
    "China": "CN",
    "India": "IN",
    "Brazil": "BR",
    "Mexico": "MX",
    "South Africa": "ZA",
    "Ireland": "IE",
    "Belgium": "BE",
    "Finland": "FI",
    "Norway": "NO",
    "New Zealand": "NZ",
    "Israel": "IL",
    "Portugal": "PT",
    "Austria": "AT",
    "Poland": "PL",
    "United Arab Emirates": "AE",
    "Saudi Arabia": "SA",
    "Thailand": "TH",
    "Indonesia": "ID",
    "Malaysia": "MY",
    "Philippines": "PH",
    "Chile": "CL",
    "Colombia": "CO",
    "Turkey": "TR",
    "Greece": "GR",
    "Czech Republic": "CZ",
    "Hungary": "HU",
    "Qatar": "QA",
    "Kuwait": "KW",
    "Egypt": "EG",
    "Morocco": "MA",
    "Russia": "RU",
    "-": "US",  # iShares uses "-" for US-listed instruments
    "": "US",
}

# Asset classes that don't represent real holdings
_SKIP_ASSET_CLASSES = {
    "Cash",
    "Money Market",
    "Futures",
    "Forward",
    "Option",
    "Other",
    "Swap",
    "Rights",
    "Warrants",
}


def _csv_url(product_id: str, slug: str, site: str = "us") -> str:
    if site == "eu":
        return (
            f"https://www.ishares.com/de/privatanleger/de/produkte/{product_id}/{slug}"
            f"/1467271812596.ajax?tab=holdings&fileType=csv"
        )
    return (
        f"https://www.ishares.com/us/products/{product_id}/{slug}"
        f"/1467271812596.ajax?tab=holdings&fileType=csv"
    )


def _download_csv(product_id: str, slug: str, site: str = "us") -> str:
    url = _csv_url(product_id, slug, site)
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    # iShares may serve with BOM; decode cleanly
    return resp.content.decode("utf-8-sig")


def _parse_holdings(csv_text: str, max_holdings: int = 150) -> tuple[list[dict], date]:
    """
    Parse iShares CSV into a list of holding dicts and the as-of date.

    iShares CSVs have several metadata rows before the actual column headers.
    We scan for the row that begins with 'Name,' to find the header.
    """
    lines = csv_text.splitlines()

    # Extract as-of date from metadata section
    as_of = date.today()
    for line in lines[:15]:
        if "Fund Holdings as of" in line or "as of" in line.lower():
            # e.g.  Fund Holdings as of,"May 21, 2026"
            parts = line.split(",", 1)
            if len(parts) == 2:
                raw_date = parts[1].strip().strip('"')
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        as_of = datetime.strptime(raw_date, fmt).date()
                        break
                    except ValueError:
                        pass
            break

    # Find the data-header row
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().strip('"')
        if stripped.startswith("Name,") or stripped.startswith("Name\t"):
            header_idx = i
            break

    if header_idx is None:
        logger.warning("Could not find data header row in iShares CSV")
        return [], as_of

    data_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(data_text))

    holdings = []
    for row in reader:
        name = row.get("Name", "").strip().strip('"')
        isin = row.get("ISIN", "").strip()
        ticker = row.get("Ticker", "").strip()
        asset_class = row.get("Asset Class", "").strip()
        weight_raw = row.get("Weight (%)", "0").replace(",", "").strip()
        location = row.get("Location", "").strip()

        # Skip non-security rows
        if not name or name.startswith("-") or asset_class in _SKIP_ASSET_CLASSES:
            continue
        # Require a valid ISIN (12 chars, starts with 2 letters)
        if len(isin) != 12 or not isin[:2].isalpha():
            continue

        try:
            weight = float(weight_raw)
        except ValueError:
            continue
        if weight <= 0:
            continue

        country_code = _COUNTRY_MAP.get(location, location[:2].upper() if len(location) >= 2 else "US")

        holdings.append(
            {
                "isin": isin,
                "name": name,
                "ticker": ticker,
                "weight": weight,
                "sector": asset_class,
                "country": country_code,
            }
        )

        if len(holdings) >= max_holdings:
            break

    return holdings, as_of


def _upsert_etf(meta: dict, db: Session) -> ETF:
    """Create or update an ETF record."""
    etf = db.query(ETF).filter_by(isin=meta["isin"]).first()
    if not etf:
        etf = ETF(
            isin=meta["isin"],
            ticker=meta["ticker"],
            name=meta["name"],
            provider="iShares",
            domicile=meta["domicile"],
            replication_method=meta["replication_method"],
            ter=meta["ter"],
            currency=meta["currency"],
            benchmark=meta["benchmark"],
        )
        db.add(etf)
        db.flush()
    else:
        etf.ticker = meta["ticker"]
        etf.name = meta["name"]
        etf.replication_method = meta["replication_method"]
        etf.ter = meta["ter"]
        etf.benchmark = meta["benchmark"]
    return etf


def _upsert_holdings(etf: ETF, holdings: list[dict], as_of: date, db: Session) -> int:
    """Delete existing holdings for this ETF+date and insert fresh ones."""
    db.query(Holding).filter_by(etf_id=etf.id, date=as_of).delete()

    for h in holdings:
        db.add(
            Holding(
                etf_id=etf.id,
                date=as_of,
                instrument_isin=h["isin"],
                instrument_name=h["name"],
                weight=h["weight"],
                sector=h["sector"],
                country=h["country"],
            )
        )
    return len(holdings)


def _upsert_allocations(etf: ETF, holdings: list[dict], as_of: date, db: Session) -> int:
    """Derive sector and country allocations from holdings weights."""
    db.query(Allocation).filter_by(etf_id=etf.id, date=as_of).delete()

    sector_weights: dict[str, float] = {}
    country_weights: dict[str, float] = {}

    for h in holdings:
        if h["sector"]:
            sector_weights[h["sector"]] = sector_weights.get(h["sector"], 0.0) + h["weight"]
        if h["country"]:
            country_weights[h["country"]] = country_weights.get(h["country"], 0.0) + h["weight"]

    count = 0
    for bucket, weight in sector_weights.items():
        db.add(Allocation(etf_id=etf.id, date=as_of, type="sector", bucket=bucket, weight=round(weight, 4)))
        count += 1
    for bucket, weight in country_weights.items():
        db.add(Allocation(etf_id=etf.id, date=as_of, type="country", bucket=bucket, weight=round(weight, 4)))
        count += 1

    return count


def import_ishares(db: Session, tickers: list[str] | None = None) -> dict:
    """
    Main entry point.  Pass tickers=None to import all 10 ETFs.
    Returns a summary dict.
    """
    targets = ISHARES_ETFS if not tickers else [e for e in ISHARES_ETFS if e["ticker"] in tickers]

    results = []
    for meta in targets:
        result = {"ticker": meta["ticker"], "status": "ok", "holdings": 0, "allocations": 0, "error": None}
        try:
            logger.info("Downloading iShares CSV for %s …", meta["ticker"])
            site = meta.get("site", "us")
            csv_text = _download_csv(meta["product_id"], meta["slug"], site)

            holdings, as_of = _parse_holdings(csv_text)
            if not holdings:
                result["status"] = "warn"
                result["error"] = "No holdings parsed from CSV"
                results.append(result)
                continue

            etf = _upsert_etf(meta, db)
            result["holdings"] = _upsert_holdings(etf, holdings, as_of, db)
            result["allocations"] = _upsert_allocations(etf, holdings, as_of, db)
            result["as_of"] = str(as_of)

            db.commit()
            logger.info("  → %s: %d holdings, %d allocation rows", meta["ticker"], result["holdings"], result["allocations"])

        except requests.HTTPError as exc:
            db.rollback()
            result["status"] = "error"
            result["error"] = f"HTTP {exc.response.status_code}"
            logger.warning("HTTP error for %s: %s", meta["ticker"], exc)
        except Exception as exc:
            db.rollback()
            result["status"] = "error"
            result["error"] = str(exc)
            logger.exception("Failed to import %s", meta["ticker"])

        results.append(result)

    total_holdings = sum(r["holdings"] for r in results)
    total_ok = sum(1 for r in results if r["status"] == "ok")
    return {"imported": total_ok, "total": len(targets), "total_holdings": total_holdings, "details": results}
