#!/usr/bin/env python3
"""UBS/iShares equity holdings and SMI reconstruction; Python 3.10+.

MULTI-INDEX PROVIDER MODE (standard library only for live iShares):
    python smi_reconstruction.py IE00B4L5Y983 --provider ishares
    python smi_reconstruction.py IE00B5BMR087 --provider ishares
    python smi_reconstruction.py IE00BD4TXV59 --provider ubs --holdings-file ubs.csv --as-of 2026-09-08
    python smi_reconstruction.py ETF_ISIN --provider ubs --holdings-url PUBLIC_UBS_CSV_URL --as-of YYYY-MM-DD
    python smi_reconstruction.py ETF_ISIN --provider ishares --product-url PUBLIC_PRODUCT_PAGE
    python astra/smi_reconstruction.py IE00B4L5Y983 --provider ishares --import-db
    python astra/smi_reconstruction.py IE00BD4TXV59 --provider ubs --holdings-file ubs.csv --as-of 2026-09-08 --import-db
--import-db uses DATABASE_URL and the project's backend dependencies to replace
the requested ETF/date holdings in PostgreSQL instead of writing holdings JSON.
The ETF must already exist. Other dates, metadata, allocations and prices are
untouched. Database weights use reported NAV percentages, not normalized weights.
Only provider mode is permitted for database imports; no synthetic/demo baskets.
Output is written automatically to holdings_<ETF_ISIN>.json; diagnostics to
diagnostics_<ETF_ISIN>.json. --output-dir changes the directory. --stdout also
prints the list for pipelines. Do not redirect to a generic holdings.json.

Supported providers are UBS and iShares, for equity ETFs tracking European
or global benchmarks. This mode reads the provider's reported equity basket;
it does NOT reconstruct MSCI/STOXX/FTSE selection rules. It does not apply the
SMI cap to other indices. Cash and derivatives are excluded. 'reported_weight'
preserves the published fraction of fund NAV; 'weight' normalizes the included
equity basket to one. Holdings of sampled or synthetic ETFs are not necessarily
their benchmark constituents. Price currencies are preserved; no FX conversion
is needed when using the issuer's already-comparable portfolio weights.

iShares: resolve the ETF ISIN through its public product search, verify the
fund's ISIN on its product page, then use that page's current holdings JSON API.
No old hard-coded .ajax CSV endpoint is used. If a share class is unavailable
in the UK product search, supply its iShares --product-url. Fail if the page
identifies another share class. ISINs come directly from the holdings API.

UBS: import the full portfolio CSV/JSON export, or supply its public download
URL. Automatic UBS ISIN-to-download discovery is NOT implemented: its fund
pages were geo-restricted during development. A local file or explicit URL
asserts that this is the requested ETF's FULL holdings export; embedded ETF
ISIN metadata, when present, is checked. Do not supply a top-ten factsheet or
a creation/redemption basket. Both providers accept these explicit sources.
CSV supports comma/semicolon/tab delimiters and English/German aliases:
ISIN, Name/Bezeichnung, Weight (%)/Gewichtung (%), Ticker, Asset Class,
Exchange, Market Currency. Percent units are the default; use --weight-unit
fraction for 0..1 inputs and --decimal-comma for comma-decimal CSVs. If asset
class is absent, explicitly assert --equities-only. JSON uses the same fields
in a holdings array, optionally with etf_isin and as_of metadata.

ISINs: every equity has 'isin' AND 'security_isin'. Invalid or missing IDs
stop the run by default. --isin-map accepts {"YAHOO_SYMBOL":"VALID_ISIN"}
for reconstruction, or {"TICKER|EXCHANGE":"VALID_ISIN"} for provider imports.
--allow-missing-isins explicitly permits null with isin_status='unresolved'.
No guessed identifiers or company-name fuzzy matches are used. SMI enrichment
also tries iShares' global equity reference data using exact Swiss ticker and
exchange, then Yahoo get_isin. Demo IDs remain null and explicitly synthetic.

SMI METHODOLOGY MODE:
    python smi_reconstruction.py CH0008899764 --mode reconstruct --allow-incomplete
    python smi_reconstruction.py --self-test
Import: get_etf_holdings(isin, provider='ishares') returns list[dict].
The legacy presumed_smi_holdings API remains available. SMI is the only
benchmark with a built-in selection-rule reconstruction engine.

The remaining documentation describes SMI reconstruction specifically.

Install for live data:
    python -m pip install "yfinance>=0.2.65,<2" "pandas>=2.2,<4" lxml
Run:
    python smi_reconstruction.py CH0008899764 --mode reconstruct --allow-incomplete
    python smi_reconstruction.py CH0008899764 --demo
    python smi_reconstruction.py --self-test
Import:
    holdings = presumed_smi_holdings("CH0008899764", allow_incomplete=True)

METHOD: SIX Swiss Index Methodology Rulebook v3.40 (8 June 2026),
sections 3.1, 4.3, 5.2, 5.12:
https://www.six-group.com/dam/download/market-data/indices/equity-indices/six-methodology-smi-equity-and-re-en.pdf
Selection uses SPI-relative 12-month average free-float capitalization and
accumulated turnover, equally weighted. Select ranks 1-18, then prefer
incumbents in ranks 19-22 to fill 20 instruments. Dual-primary listings with
under 50% SIX turnover require liquidity rank <=18 for entry, <=22 to remain.
Cap issuer weights at 18%, redistributing proportionally across issuers and
then across their instruments. Selection is annual, using July-June data for
September implementation. The official quarterly cap can drift; an ad-hoc
reset follows two constituents exceeding 20%. This script returns freshly
capped weights, not a replay of that schedule.

WHAT THE LIVE ESTIMATE ASSUMES:
* Yahoo's Swiss exchange screener approximates the SPI. Currency-suffixed
  trading lines and known non-CHF/non-domestic/non-equity records are excluded
  before downloading prices. This is an approximation, not SPI certification.
  An eligible=True override can retain eligible foreign issuers (CHF required).
  Missing eligibility metadata is a data failure, not an automatic exclusion.
  A broad candidate
  list is the explicit fallback if discovery fails; it is NOT an SMI list.
* Swiss/Liechtenstein domicile, equity type and >=20% estimated float proxy
  SPI eligibility. This misses eligible foreign issuers, admission delays,
  investment-company exceptions and SIX's discretionary classifications.
* Yahoo floatShares/sharesOutstanding is NOT SIX free float. Missing float
  uses 1-heldPercentInsiders, then an explicit 100% assumption. Institutional
  holdings are NOT automatically subtracted. Supply class-specific overrides
  for issuers with several share classes: vendor totals can be consolidated.
* Current shares and float are held constant over the review window. This
  introduces look-ahead and corporate-action errors. Yahoo split-adjusted
  Close (without dividend adjustment) times reported Volume proxies turnover;
  it does not identify official SIX order-book transactions or exact VWAP.
* Missing sharesOutstanding tries recent share-count observations, fast_info
  shares, then marketCap/regularMarketPrice for non-known-multiclass issuers.
  The last option is an explicit approximation with its source on the holding.
  No numeric fallback is invented when all sources fail.
* Known IPO dates trigger removal of the first five observed sessions and
  annualization of turnover. Weekdays proxy a full-year session count.
* Live incumbents come from a public SMI table, not the official review file.
  Their use with the latest completed June window is a REVIEW SIMULATION,
  not a historical reconstruction or an assertion of today's official basket.
* Prices come from the latest completed day; capitalization used for weights
  is separate from average capitalization used for selection. No cash,
  derivatives, fees, lending, sampling or ETF-specific positions are modeled.
* Network/data errors are never converted into invented market observations.
  Missing candidates stop the run unless allow_incomplete is explicitly set.
  Demo data are synthetic and are never used as a network fallback.

BETTER INPUTS (no third-party packages needed):
    python smi_reconstruction.py CH0008899764 --snapshot inputs.json
Snapshot JSON: {"selection_cutoff":"2026-06-30",
 "weighting_date":"2026-09-08", "universe_source":"your SPI data export",
 "notes":[], "securities":[...one record per instrument...]}
Required record keys are Security's fields through 'incumbent' below.
avg_ff_cap_chf is the window average; turnover_chf is the window total;
weight_ff_cap_chf is point-in-time capitalization for weighting. Supply the
FULL SPI universe, including ineligible-for-SMI dual-primary instruments,
with historical SPI eligibility and pre-review incumbents already resolved.
Set eligible=False for records outside SPI. For multiple-primary listings,
primary_turnover_chf must aggregate only primary venues, converted to CHF;
six_turnover_share is SIX turnover / global turnover. For other instruments,
primary turnover defaults to turnover_chf. security_isin may be null.
Use --save-snapshot inputs.json after a live run to get this exact schema.

Overrides JSON maps Yahoo symbol to any of:
  {"ROG.SW":{"shares_outstanding":123, "free_float_factor":1.0,
    "issuer_id":"ROCHE", "security_isin":"...", "eligible":true,
    "multiple_primary":false, "listing_date":"YYYY-MM-DD"}}
The 123 is a SCHEMA EXAMPLE, not a real share count. Unknown keys are errors.
Use --incumbents incumbents.json with a JSON array of 20 Yahoo symbols for
an audited pre-review constituent set. --universe universe.json accepts an
array of symbols, replacing screener discovery. --assume-smi explicitly
asserts an unknown ETF's benchmark; the script cannot infer it from its ISIN.

Public provider: https://ranaroussi.github.io/yfinance/reference/index.html
ETF mapping: iShares SMI ETF (CH), CH0008899764, benchmark SMIC:
https://www.ishares.com/ch/individual/en/products/251780/ishares-smi-ch-fund
Live adapters are best-effort third-party integrations, not licensed SIX APIs.
Audit summaries are returned on every holding; detailed diagnostics go to
stderr and optionally --diagnostics diagnostics.json (also saved in snapshots).
The full universe error list is NOT duplicated inside each holding. The
CLI writes an ETF-specific JSON file; --stdout additionally prints the list.
Weights are fractions, not percentages.
"""

from __future__ import annotations

import argparse
import calendar
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from html.parser import HTMLParser
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urlencode

LOG = logging.getLogger("smi")
ETF_REGISTRY = {"CH0008899764": "iShares SMI ETF (CH)"}
FALLBACK_SYMBOLS = """ABBN ALC ADEN AMRZ AMS AROUN BARN BALN BALO BEAN BELL
 BKW BUCN CFT CFR CLN COTN CPG DOKA DORN EFGN EMSN FHNW GALD GEBN GF
 GIVN HELN HBMN HIAG HOLN HUBN IMPN INRN KNIN LAND LISP LISN LOGN LONN METN
 MOBN NESN NOVN OERL PGHN PSPN RICN ROG ROP RO SCHN SCHP SCMN SFPN SGSN
 SIKA SIGN SLHN SOON SQN SRAIL SREN STMN STRN SUN SWON SWSN TECN TEMN UBSG UHR
 UHRN VONN VATN VETN YPSN ZURN""".split()
# These aliases merge issuer exposure for the cap, not security selection.
ISSUER_ALIASES = {"ROG": "ROCHE", "ROP": "ROCHE", "RO": "ROCHE", "LISP": "LINDT",
                  "LISN": "LINDT", "SCHN": "SCHINDLER", "SCHP": "SCHINDLER",
                  "UHR": "SWATCH", "UHRN": "SWATCH"}
MULTICLASS = set(ISSUER_ALIASES) | {"CFR"}


class ExcludedCandidate(Exception):
    """Outside the documented live universe proxy, rather than missing data."""


def check_candidate(symbol: str, info: dict, override: dict, incumbent: bool = False,
                    require_metadata: bool = False) -> None:
    """Filter before price/share requests, including when an old cache is used.

    Preserve a distinction between deliberate exclusions and unresolved data.
    An incumbent rejected by this proxy requires investigation, not a silent
    removal. A user eligible=True override bypasses domicile/type heuristics.
    """
    if "eligible" in override and type(override["eligible"]) is not bool:
        raise ValueError("eligible override must be a JSON boolean")
    if override.get("eligible") is False:
        raise ExcludedCandidate("Excluded by user eligibility override")
    explicit = override.get("eligible") is True
    reason = None
    if not explicit and re.search(r"-(?:USD|EUR|GBP|CHF|JPY|CAD|AUD)\.SW$", symbol):
        reason = "Currency-suffixed trading line outside the domestic-equity proxy"
    elif info.get("currency") and info["currency"] != "CHF":
        reason = "Non-CHF quote; use a converted snapshot if this instrument is eligible"
    elif not explicit and info.get("quoteType") and info["quoteType"] != "EQUITY":
        reason = "Non-equity quote type"
    elif not explicit and info.get("country") and info["country"] not in {"Switzerland", "Liechtenstein"}:
        reason = "Foreign domicile outside the domestic-equity proxy; eligible=True can override"
    if reason:
        if incumbent or explicit:
            raise ValueError("Candidate eligibility needs review: " + reason)
        raise ExcludedCandidate(reason)
    if require_metadata:
        required = ("currency",) if explicit else ("currency", "country", "quoteType")
        missing = [key for key in required if not info.get(key)]
        if missing:
            raise ValueError("Missing eligibility metadata: " + ", ".join(missing))


def resolve_shares(yf, symbol: str, info: dict, override: dict,
                   weighting: date) -> tuple[float, str]:
    """Recover absent vendor shares without substituting float for total shares."""
    if "shares_outstanding" in override:
        value = override["shares_outstanding"]
        if not positive(value):
            raise ValueError("shares_outstanding override must be positive")
        return float(value), "User-supplied class-level share count."
    if positive(info.get("sharesOutstanding")):
        return float(info["sharesOutstanding"]), "Share count from Yahoo sharesOutstanding."
    ticker = yf.Ticker(symbol)
    problems = []
    try:
        history = ticker.get_shares_full(start=(weighting - timedelta(days=180)).isoformat(),
                                         end=(weighting + timedelta(days=1)).isoformat())
        if history is not None and not history.empty:
            values = [(stamp, float(value)) for stamp, value in history.items()
                      if (weighting - timedelta(days=180)) <= stamp.date() <= weighting
                      and positive(float(value))]
            if values:
                stamp, value = sorted(values, key=lambda item: item[0])[-1]
                return value, f"Share count from Yahoo share-count history dated {stamp.date()}."
    except Exception as exc:
        if type(exc).__name__ == "YFRateLimitError":
            raise
        problems.append(type(exc).__name__)
    try:
        value = ticker.get_fast_info()["shares"]
        if value is not None and positive(float(value)):
            return float(value), "Share count from Yahoo fast_info shares (current observation)."
    except Exception as exc:
        if type(exc).__name__ == "YFRateLimitError":
            raise
        problems.append(type(exc).__name__)
    # Use the price accompanying marketCap, never an unrelated historic close.
    # Issuer-wide caps can misstate a class's share count; prohibit the fallback
    # for known multiple-class issuers and warn for other vendor records.
    if symbol.removesuffix(".SW") not in MULTICLASS:
        cap, price = info.get("marketCap"), info.get("regularMarketPrice")
        if info.get("currency") == "CHF" and positive(cap) and positive(price) and positive(cap / price):
            return cap / price, ("APPROXIMATED share count = Yahoo marketCap / regularMarketPrice; "
                                 "assumes both refer to the same share class and valuation time.")
    raise ValueError("No usable share count from info, share history or fast_info; "
                     "no safe market-cap/price fallback. Supply shares_outstanding override. "
                     + ("Provider errors: " + ", ".join(problems) if problems else ""))


@dataclass
class Security:
    symbol: str
    name: str
    issuer_id: str
    security_isin: str | None
    avg_ff_cap_chf: float
    turnover_chf: float
    weight_ff_cap_chf: float
    free_float_factor: float
    eligible: bool
    incumbent: bool
    multiple_primary: bool = False
    six_turnover_share: float = 1.0
    primary_turnover_chf: float | None = None
    price_date: str | None = None
    notes: list[str] | None = None


def validate_isin(value: str) -> str:
    """Validate ISO-style syntax and the Luhn check digit, not the issuer."""
    if not isinstance(value, str):
        raise ValueError("ISIN must be a string")
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
        raise ValueError(f"Invalid ISIN syntax: {value}")
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in value)
    total = 0
    for i, c in enumerate(reversed(digits)):
        n = int(c) * (2 if i % 2 else 1)
        total += n // 10 + n % 10
    if total % 10:
        raise ValueError(f"Invalid ISIN check digit: {value}")
    return value


def resolve_etf(isin: str, assume_smi: bool = False) -> tuple[str, str]:
    isin = validate_isin(isin)
    if isin in ETF_REGISTRY:
        return isin, ETF_REGISTRY[isin]
    if not assume_smi:
        raise ValueError("Unknown ETF ISIN. Verify its benchmark, then use "
                         "assume_smi=True / --assume-smi if it tracks SMI.")
    return isin, "User-asserted SMI-tracking ETF"


def positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def validate_security(s: Security) -> None:
    if not all(isinstance(x, str) and x.strip() for x in (s.symbol, s.name, s.issuer_id)):
        raise ValueError("symbol, name and issuer_id must be nonempty strings")
    if any(type(x) is not bool for x in (s.eligible, s.incumbent, s.multiple_primary)):
        raise ValueError(f"{s.symbol}: eligibility/incumbency fields must be JSON booleans")
    for key in ("avg_ff_cap_chf", "weight_ff_cap_chf"):
        if not positive(getattr(s, key)):
            raise ValueError(f"{s.symbol}: invalid {key}")
    for key in ("turnover_chf", "primary_turnover_chf"):
        val = getattr(s, key)
        if key == "primary_turnover_chf" and val is None and not s.multiple_primary:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0:
            raise ValueError(f"{s.symbol}: invalid or missing {key}")
    if not positive(s.free_float_factor) or s.free_float_factor > 1:
        raise ValueError(f"{s.symbol}: float must be in (0,1]")
    if not isinstance(s.six_turnover_share, (int, float)) or not math.isfinite(s.six_turnover_share) or not 0 <= s.six_turnover_share <= 1:
        raise ValueError(f"{s.symbol}: invalid SIX turnover share")
    if s.security_isin is not None:
        validate_isin(s.security_isin)
    if s.notes is not None and (not isinstance(s.notes, list) or any(not isinstance(n, str) for n in s.notes)):
        raise ValueError(f"{s.symbol}: notes must be strings")


def capped_weights(capitalizations: dict[str, float], cap: float = 0.18) -> dict[str, float]:
    """Water filling: freeze cap breaches and reallocate to uncapped names.

    Do not clip and normalize: normalization would breach the cap again.
    Input keys here are ISSUERS. Reject infeasible baskets and invalid numbers.
    """
    if not positive(cap) or cap > 1 or not capitalizations:
        raise ValueError("Invalid cap or empty basket")
    if any(not positive(v) for v in capitalizations.values()):
        raise ValueError("Capitalizations must be positive finite numbers")
    if len(capitalizations) * cap < 1 - 1e-12:
        raise ValueError("Too few issuers for the requested cap")
    # Scale first so summing extremely large inputs cannot overflow.
    scale = max(capitalizations.values())
    remaining = {k: v / scale for k, v in capitalizations.items()}
    result: dict[str, float] = {}
    budget = 1.0
    while remaining:
        denominator = math.fsum(remaining.values())
        proposed = {k: budget * v / denominator for k, v in remaining.items()}
        breaches = [k for k, w in proposed.items() if w > cap + 1e-14]
        if not breaches:
            result.update(proposed)
            break
        for k in breaches:
            result[k] = cap
            del remaining[k]
        budget = 1.0 - math.fsum(result.values())
    if abs(math.fsum(result.values()) - 1) > 1e-10 or max(result.values()) > cap + 1e-10:
        raise ArithmeticError("Capping did not converge")
    return result


def select_components(securities: list[Security]) -> tuple[list[Security], dict[str, dict]]:
    """Compute score over SPI first; apply dual-primary tests without changing denominators.

    eligible is an upstream SPI-membership decision. Do not reapply a spot
    float threshold here: an official SPI input can reflect its grace period.
    Equal scores use capitalization then symbol as a documented deterministic
    tie-break approximation. Special corporate-action decisions are upstream.
    """
    for s in securities:
        validate_security(s)
    if len({s.symbol for s in securities}) != len(securities):
        raise ValueError("Duplicate symbols in the universe")
    isins = [s.security_isin for s in securities if s.security_isin]
    if len(set(isins)) != len(isins):
        raise ValueError("Duplicate security ISINs in the universe")
    universe = [s for s in securities if s.eligible]
    if len(universe) < 20:
        raise ValueError(f"Need at least 20 eligible instruments; have {len(universe)}")
    total_cap = math.fsum(s.avg_ff_cap_chf for s in universe)
    total_turnover = math.fsum(s.turnover_chf for s in universe)
    if total_turnover <= 0:
        raise ValueError("Universe has no turnover")
    metrics = {s.symbol: {"selection_score": 0.5 * (s.avg_ff_cap_chf / total_cap + s.turnover_chf / total_turnover)} for s in universe}
    ordered = sorted(universe, key=lambda s: (-metrics[s.symbol]["selection_score"], -s.avg_ff_cap_chf, s.symbol))
    liquidity = sorted(universe, key=lambda s: (-(s.primary_turnover_chf if s.primary_turnover_chf is not None else s.turnover_chf), s.symbol))
    for rank, s in enumerate(liquidity, 1):
        metrics[s.symbol]["liquidity_rank"] = rank
    for rank, s in enumerate(ordered, 1):
        metrics[s.symbol]["selection_rank"] = rank

    def can_enter(s: Security) -> bool:
        if s.multiple_primary and s.six_turnover_share < 0.5:
            return metrics[s.symbol]["liquidity_rank"] <= (22 if s.incumbent else 18)
        return True

    selected = [s for s in ordered[:18] if can_enter(s)]
    buffer = ordered[18:22]
    for group in ([s for s in buffer if s.incumbent], [s for s in buffer if not s.incumbent]):
        for s in group:
            if len(selected) < 20 and can_enter(s):
                selected.append(s)
    if len(selected) != 20:
        # Do not invent a rank>22 promotion convention in an exceptional case.
        raise ValueError("Selection rules did not fill 20 places. Supply SIX's "
                         "exceptional-review decision or corrected liquidity inputs.")
    return selected, metrics


def build_holdings(etf_isin: str, securities: list[Security], metadata: dict,
                   assume_smi: bool = False) -> list[dict[str, Any]]:
    """Return the requested list of dictionaries, with audit fields attached."""
    isin, name = resolve_etf(etf_isin, assume_smi)
    selected, scores = select_components(securities)
    issuer_caps: dict[str, float] = {}
    for s in selected:
        issuer_caps[s.issuer_id] = issuer_caps.get(s.issuer_id, 0) + s.weight_ff_cap_chf
    issuer_weights = capped_weights(issuer_caps)
    # A common scaling makes every capping factor <=1. Only relative factors
    # affect weights. The result is not an official SIX-published factor.
    ratios = {k: issuer_weights[k] / v for k, v in issuer_caps.items()}
    normalizer = max(ratios.values())
    output = []
    for s in selected:
        weight = issuer_weights[s.issuer_id] * s.weight_ff_cap_chf / issuer_caps[s.issuer_id]
        output.append({
            "etf_isin": isin, "etf_name": name, "benchmark": "SMI",
            "symbol": s.symbol, "name": s.name, "security_isin": s.security_isin,
            "issuer_id": s.issuer_id, "weight": weight,
            "issuer_weight": issuer_weights[s.issuer_id],
            "estimated_capping_factor": ratios[s.issuer_id] / normalizer,
            "free_float_factor": s.free_float_factor,
            "average_free_float_market_cap_chf": s.avg_ff_cap_chf,
            "weighting_free_float_market_cap_chf": s.weight_ff_cap_chf,
            "turnover_chf": s.turnover_chf, "incumbent": s.incumbent,
            **scores[s.symbol], "selection_cutoff": metadata["selection_cutoff"],
            "weighting_date": metadata["weighting_date"], "price_date": s.price_date,
            "universe_size": len(securities), "eligible_universe_size": sum(x.eligible for x in securities),
            "universe_source": metadata["universe_source"],
            "estimate_type": "synthetic_demo" if metadata.get("demo") else "presumed_review_basket_freshly_capped",
            "is_actual_etf_holding": False,
            "assumptions": list(metadata.get("notes", [])) + list(s.notes or []),
        })
    output.sort(key=lambda x: (-x["weight"], x["symbol"]))
    if abs(math.fsum(h["weight"] for h in output) - 1) > 1e-10:
        raise ArithmeticError("Weights do not sum to one")
    return output


def read_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_snapshot(path: str | Path) -> tuple[list[Security], dict]:
    obj = read_json(path)
    for key in ("selection_cutoff", "weighting_date", "universe_source", "securities"):
        if key not in obj:
            raise ValueError(f"Snapshot missing {key}")
    cutoff = date.fromisoformat(obj["selection_cutoff"])
    weighting = date.fromisoformat(obj["weighting_date"])
    if cutoff > weighting:
        raise ValueError("Selection cutoff cannot follow weighting date")
    if not isinstance(obj.get("notes", []), list) or any(not isinstance(n, str) for n in obj.get("notes", [])):
        raise ValueError("Snapshot notes must be a list of strings")
    securities = [Security(**row) for row in obj["securities"]]
    return securities, {k: v for k, v in obj.items() if k != "securities"}


def save_snapshot(path: str | Path, securities: list[Security], metadata: dict) -> None:
    Path(path).write_text(json.dumps({**metadata, "securities": [asdict(s) for s in securities]}, indent=2, allow_nan=False), encoding="utf-8")


def retry(call, attempts: int = 3):
    """Bounded backoff; retain the final provider error for diagnostics."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            # Repeated immediate requests only prolong provider throttling.
            if type(exc).__name__ == "YFRateLimitError":
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def discover_universe(yf) -> tuple[list[str], str, list[str]]:
    """Page through Yahoo's EBS equities; never truncate to the current SMI."""
    try:
        query = yf.EquityQuery("eq", ["exchange", "EBS"])
        symbols: set[str] = set()
        offset = 0
        while True:
            result = retry(lambda: yf.screen(query, offset=offset, size=250,
                            sortField="intradaymarketcap", sortAsc=False))
            quotes = result.get("quotes", [])
            if not quotes:
                if offset < int(result.get("total", 0)):
                    raise ValueError("Screener returned an incomplete page")
                break
            symbols.update(q["symbol"] for q in quotes if q.get("symbol", "").endswith(".SW"))
            offset += len(quotes)
            if offset >= int(result.get("total", offset)):
                break
            if offset > 10000:
                raise ValueError("Unexpected screener pagination")
        if len(symbols) < 40:
            raise ValueError(f"Suspiciously small screener universe: {len(symbols)}")
        return sorted(symbols), "Yahoo EBS equity screener (SPI approximation)", []
    except Exception as exc:
        note = f"Screener unavailable ({type(exc).__name__}); broad static candidate fallback omits smaller/new listings."
        LOG.warning(note)
        return [s + ".SW" for s in FALLBACK_SYMBOLS], "Embedded broad Swiss candidate universe", [note]


def fetch_incumbents() -> set[str]:
    """Best-effort current membership, not a historical constituent database."""
    import pandas as pd
    request = Request("https://en.wikipedia.org/wiki/Swiss_Market_Index",
                      headers={"User-Agent": "SMIResearch/1.0 (public index research)"})
    def fetch():
        with urlopen(request, timeout=25) as response:
            return response.read().decode("utf-8")
    tables = pd.read_html(StringIO(retry(fetch)))
    for table in tables:
        cols = {str(c).lower(): c for c in table.columns}
        ticker_col = next((v for k, v in cols.items() if "ticker" in k or "symbol" in k), None)
        # The live table currently has Name/Sector/Ticker/Rank, but no ISIN.
        # Require constituent-specific columns so an unrelated 20-row table
        # cannot accidentally become the incumbent set.
        if ticker_col is None or not any(k in cols for k in ("name", "company")) or "sector" not in cols:
            continue
        symbols = set()
        for cell in table[ticker_col].dropna():
            match = re.fullmatch(r"([A-Z][A-Z0-9]{1,7})(?:\.SW)?(?:\[.*\])?", str(cell).strip())
            if match:
                symbols.add(match.group(1) + ".SW")
        if len(symbols) == 20:
            return symbols
    raise ValueError("Could not identify a validated 20-row incumbent table")


def quote_inputs(yf, symbol: str, start: date, end: date, cache_dir: Path,
                 eligibility_check=None) -> tuple[dict, Any]:
    """Cache current metadata and daily observations for 12 hours, keyed by window."""
    import pandas as pd
    if not re.fullmatch(r"[A-Z0-9.-]+\.SW", symbol):
        raise ValueError(f"Unexpected Swiss Yahoo symbol: {symbol}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol}_{start}_{end}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 43200:
        try:
            cached = read_json(path)
            history = pd.DataFrame(cached["history"]).set_index("Date")
            history.index = pd.to_datetime(history.index)
        except (ValueError, KeyError):
            LOG.warning("Ignoring damaged cache for %s", symbol)
        else:
            # Do not mistake an eligibility rejection for cache corruption.
            if eligibility_check is not None:
                eligibility_check(cached["info"])
            return cached["info"], history
    ticker = yf.Ticker(symbol)
    info = retry(ticker.get_info)
    if eligibility_check is not None:
        eligibility_check(info)
    history = retry(lambda: ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                          auto_adjust=False, actions=False, raise_errors=True, timeout=25))
    if history.empty:
        raise ValueError("Empty daily history")
    history.index = history.index.tz_localize(None).normalize()
    history = history[["Close", "Volume"]].copy()
    # json default handles numpy scalars if a provider returns them in info.
    records = [{"Date": d.date().isoformat(), "Close": float(r.Close), "Volume": float(r.Volume)}
               for d, r in history.iterrows() if math.isfinite(r.Close) and math.isfinite(r.Volume)]
    if not records:
        raise ValueError("No finite observations")
    payload = {"info": info, "history": records}
    path.write_text(json.dumps(payload, default=lambda x: x.item(), allow_nan=False), encoding="utf-8")
    return info, history


def fetch_security(yf, symbol: str, start: date, cutoff: date, weighting: date,
                   incumbents: set[str], override: dict, cache_dir: Path) -> Security:
    permitted = {"shares_outstanding", "free_float_factor", "issuer_id", "security_isin",
                 "eligible", "multiple_primary", "six_turnover_share", "primary_turnover_chf", "listing_date"}
    if set(override) - permitted:
        raise ValueError(f"Unknown overrides: {sorted(set(override) - permitted)}")
    check_candidate(symbol, {}, override, symbol in incumbents)
    import pandas as pd
    info, history = quote_inputs(yf, symbol, start, weighting, cache_dir,
        eligibility_check=lambda info: check_candidate(symbol, info, override,
                                                       symbol in incumbents, True))
    notes = ["Yahoo daily Close*Volume approximates SIX order-book turnover.",
             "Current share count and float held constant over selection window."]
    shares, share_note = resolve_shares(yf, symbol, info, override, weighting)
    notes.append(share_note)
    if "free_float_factor" in override:
        ff = override["free_float_factor"]
        notes.append("Free float supplied by user override.")
    elif positive(info.get("floatShares")) and info["floatShares"] <= shares:
        ff = info["floatShares"] / shares
        notes.append("Free float approximated from Yahoo floatShares/sharesOutstanding.")
    elif isinstance(info.get("heldPercentInsiders"), (int, float)) and 0 <= info["heldPercentInsiders"] < 1:
        ff = 1 - info["heldPercentInsiders"]
        notes.append("Missing/inconsistent float shares: using 1 minus insider fraction.")
    else:
        ff = 1.0
        notes.append("NO FREE-FLOAT DATA: assumed 100% free float.")
    if not positive(ff) or ff > 1:
        raise ValueError("Invalid free float override")
    base = symbol.removesuffix(".SW")
    if base in MULTICLASS and "shares_outstanding" not in override:
        notes.append("MULTIPLE SHARE CLASSES: Yahoo shares may be issuer-wide; supply a class-specific share count.")
    history = history[history["Close"].gt(0) & history["Volume"].ge(0)].dropna()
    window = history.loc[start.isoformat():cutoff.isoformat()]
    if window.empty:
        raise ValueError("No observations in July-June selection window")
    listing = override.get("listing_date")
    if listing is None and positive(info.get("firstTradeDateEpochUtc")):
        listing = datetime.fromtimestamp(info["firstTradeDateEpochUtc"], timezone.utc).date().isoformat()
    ipo = listing is not None and start <= date.fromisoformat(listing) <= cutoff
    if ipo:
        if (window.index[0].date() - date.fromisoformat(listing)).days > 10:
            raise ValueError("IPO observations do not start near listing date")
        window = window.iloc[5:]
        notes.append("IPO: removed first five observed sessions; turnover annualized using weekday count.")
    elif len(window) < 180 or (window.index[0].date() - start).days > 10 or (cutoff - window.index[-1].date()).days > 10:
        raise ValueError("Incomplete selection history; provide listing date for an IPO or corrected data")
    if len(window) < 20:
        raise ValueError("Insufficient post-IPO data; extraordinary admissions are not modeled")
    turnover = float((window["Close"] * window["Volume"]).sum())
    if ipo:
        turnover *= len(pd.bdate_range(start, cutoff)) / len(window)
    price_date = history.index[-1].date()
    if (weighting - price_date).days > 7:
        raise ValueError(f"Stale weighting price from {price_date}")
    eligible = override.get("eligible", info.get("quoteType") == "EQUITY"
                            and info.get("country") in {"Switzerland", "Liechtenstein"} and ff >= 0.2)
    if "eligible" not in override:
        notes.append("SPI eligibility proxied by domicile, equity type and spot float >=20%; SPI exceptions not resolved.")
    if "multiple_primary" not in override:
        notes.append("Single primary listing assumed; supply cross-venue liquidity data if applicable.")
    result = Security(symbol=symbol, name=info.get("longName") or info.get("shortName") or symbol,
        issuer_id=override.get("issuer_id", ISSUER_ALIASES.get(base, base)),
        security_isin=override.get("security_isin"),
        avg_ff_cap_chf=float(window["Close"].mean()) * shares * ff,
        turnover_chf=turnover, weight_ff_cap_chf=float(history["Close"].iloc[-1]) * shares * ff,
        free_float_factor=ff, eligible=eligible, incumbent=symbol in incumbents,
        multiple_primary=override.get("multiple_primary", False),
        six_turnover_share=override.get("six_turnover_share", 1.0),
        primary_turnover_chf=override.get("primary_turnover_chf"),
        price_date=price_date.isoformat(), notes=notes)
    validate_security(result)
    return result


def live_inputs(*, universe: list[str] | None = None, incumbents: set[str] | None = None,
                overrides: dict | None = None, allow_incomplete: bool = False,
                cache_dir: str | Path = ".smi_cache", workers: int = 3,
                diagnostics_path: str | Path | None = None) -> tuple[list[Security], dict]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install live dependencies: python -m pip install yfinance pandas lxml") from exc
    weighting = datetime.now(timezone.utc).date() - timedelta(days=1)
    cutoff = date(weighting.year, 6, 30)
    if cutoff > weighting:
        cutoff = date(weighting.year - 1, 6, 30)
    start = date(cutoff.year - 1, 7, 1)
    notes = ["Review simulation using latest completed July-June window; not historical or confirmed current composition.",
             "Fresh 18% issuer cap at observed prices; official quarterly factors and subsequent drift not replayed.",
             "Public sources approximate SPI eligibility, SIX free float and turnover; ETF holdings can differ."]
    if universe is None:
        universe, source, discovery_notes = discover_universe(yf)
        notes.extend(discovery_notes)
    else:
        source = "User-supplied universe; Yahoo market observations"
    if len(set(universe)) != len(universe):
        raise ValueError("Duplicate symbols in requested universe")
    if incumbents is None:
        try:
            incumbents = fetch_incumbents()
            notes.append("Current SMI table used for incumbent buffer; replace with audited pre-review membership.")
        except Exception as exc:
            if not allow_incomplete:
                raise RuntimeError("Incumbent discovery failed; supply --incumbents or explicitly --allow-incomplete") from exc
            incumbents = set()
            notes.append("INCUMBENTS UNAVAILABLE: no incumbency preference; selection reduces to top 20 eligible ranks.")
    elif len(incumbents) != 20:
        raise ValueError("Supply exactly 20 incumbent instrument symbols")
    missing_incumbents = incumbents - set(universe)
    if missing_incumbents:
        notes.append("Incumbents missing from discovery added to candidate universe: " + ", ".join(sorted(missing_incumbents)))
        universe = sorted(set(universe) | incumbents)
    overrides = overrides or {}
    if set(overrides) - set(universe):
        raise ValueError("Overrides contain symbols outside the requested universe")
    LOG.info("Fetching %d candidates for %s through %s", len(universe), start, cutoff)
    securities, errors, excluded = [], {}, {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = {pool.submit(fetch_security, yf, symbol, start, cutoff, weighting,
                   incumbents, overrides.get(symbol, {}), Path(cache_dir)): symbol for symbol in universe}
        for n, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            try:
                securities.append(future.result())
            except ExcludedCandidate as exc:
                excluded[symbol] = str(exc)
                LOG.debug("%s excluded: %s", symbol, exc)
            except Exception as exc:
                if type(exc).__name__ == "YFRateLimitError":
                    for pending in futures:
                        pending.cancel()
                    raise RuntimeError("Yahoo rate-limited the session. Retry later or use "
                                       "a saved input snapshot; no live holdings were produced.") from exc
                errors[symbol] = f"{type(exc).__name__}: {exc}"
                LOG.warning("%s failed: %s", symbol, errors[symbol])
            if n % 20 == 0:
                LOG.info("Processed %d/%d candidates", n, len(universe))
    # Detailed run-level diagnostics are kept once, not on each holding.
    diagnostics = {"requested_count": len(universe), "fetched_count": len(securities),
                   "excluded_count": len(excluded), "failed_count": len(errors),
                   "excluded_candidates": dict(sorted(excluded.items())),
                   "failed_candidates": dict(sorted(errors.items()))}
    if diagnostics_path is not None:
        Path(diagnostics_path).write_text(json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
    LOG.info("Universe: %d fetched, %d excluded by eligibility proxy, %d unresolved failures",
             len(securities), len(excluded), len(errors))
    if excluded:
        notes.append(f"Excluded {len(excluded)} candidates outside the documented eligibility proxy.")
    if errors:
        if not allow_incomplete:
            raise RuntimeError(f"{len(errors)} candidates have unresolved data failures; "
                               "see stderr or --diagnostics output. Correct inputs or explicitly "
                               "use --allow-incomplete for an incomplete estimate.")
        notes.append(f"INCOMPLETE UNIVERSE: {len(errors)} unresolved candidates omitted; details in run diagnostics.")
    securities.sort(key=lambda s: s.symbol)
    return securities, {"selection_cutoff": cutoff.isoformat(), "weighting_date": weighting.isoformat(),
                        "universe_source": source, "notes": notes, "diagnostics": diagnostics}


def presumed_smi_holdings(etf_isin: str, *, snapshot: str | Path | None = None,
                         assume_smi: bool = False, save_inputs: str | Path | None = None,
                         isin_map: dict | None = None, allow_missing_isins: bool = False,
                         **live_options) -> list[dict[str, Any]]:
    """Public API. Snapshot mode is offline; live mode accepts live_inputs options."""
    resolve_etf(etf_isin, assume_smi)  # Reject wrong identifiers before network I/O.
    if snapshot is not None and live_options:
        raise ValueError("Do not combine a snapshot with live-data options")
    securities, metadata = load_snapshot(snapshot) if snapshot is not None else live_inputs(**live_options)
    holdings = build_holdings(etf_isin, securities, metadata, assume_smi)
    if not metadata.get("demo"):
        holdings = enrich_smi_isins(holdings, isin_map=isin_map, allow_missing=allow_missing_isins,
                                   cache_dir=live_options.get("cache_dir", ".smi_cache"))
        resolved = {h["symbol"]: h["security_isin"] for h in holdings}
        for security in securities:
            if security.symbol in resolved:
                security.security_isin = resolved[security.symbol]
    if save_inputs is not None:
        save_snapshot(save_inputs, securities, metadata)
    return holdings


def demo_inputs() -> tuple[list[Security], dict]:
    """Synthetic observations: executable offline example, not Swiss market data."""
    securities = []
    for i in range(1, 31):
        cap = 1e9 * (31 - i) ** 2
        if i <= 2:
            cap *= 9
        securities.append(Security(f"DEMO{i:02d}.SW", f"Synthetic company {i}", f"DEMO{i:02d}",
                         None, cap, cap * 0.3, cap, 0.8, True, i <= 18 or i in (21, 22)))
    return securities, {"selection_cutoff": "2026-06-30", "weighting_date": "2026-09-08",
                         "universe_source": "SYNTHETIC DEMONSTRATION", "demo": True,
                         "notes": ["All demo companies and market observations are invented for testing."]}


def self_test() -> None:
    """Offline regression tests for consequential selection and allocation cases."""
    import random
    import tempfile
    import unittest
    from types import SimpleNamespace, ModuleType
    from unittest.mock import Mock, patch

    class Tests(unittest.TestCase):
        def test_provider_weights_isins_and_exclusions(self):
            rows = [{"Name": "Apple", "ISIN": "US0378331005", "Weight (%)": 60,
                     "Asset Class": "Equity", "Ticker": "AAPL", "Exchange": "NASDAQ"},
                    {"Name": "Microsoft", "ISIN": "US5949181045", "Weight (%)": 39,
                     "Asset Class": "Equity", "Ticker": "MSFT", "Exchange": "NASDAQ"},
                    {"Name": "USD Cash", "Weight (%)": 1, "Asset Class": "Cash"}]
            meta = {"provider": "ubs", "source": "synthetic regression fixture", "as_of": "2026-09-08"}
            holdings, diag = normalize_provider_holdings("IE00BD4TXV59", rows, meta)
            self.assertEqual(len(holdings), 2)
            self.assertAlmostEqual(sum(h["weight"] for h in holdings), 1)
            self.assertEqual(holdings[0]["reported_weight"], 0.6)
            self.assertEqual(holdings[0]["isin"], "US0378331005")
            self.assertEqual(len(diag["excluded_positions"]), 1)
            rows[0]["ISIN"] = None
            with self.assertRaises(ValueError):
                normalize_provider_holdings("IE00BD4TXV59", rows, meta)
            holdings, _ = normalize_provider_holdings("IE00BD4TXV59", rows, meta,
                isin_map={"AAPL|NASDAQ": "US0378331005"})
            self.assertTrue(all(h["isin"] for h in holdings))
            rows[0]["Weight (%)"] = 5
            with self.assertRaises(ValueError):
                normalize_provider_holdings("IE00BD4TXV59", rows, meta, allow_missing_isins=True)

        def test_provider_export_formats_and_file_names(self):
            csv_data = ('Fonds ISIN;IE00BD4TXV59\nStichtag;08.09.2026\n'
                'Bezeichnung;ISIN;Gewichtung (%);Anlageklasse\n'
                'Apple;US0378331005;60,5;Aktien\nMicrosoft;US5949181045;39,5;Aktien\n').encode()
            rows, meta = read_provider_export(csv_data)
            meta.update(provider="ubs", source="synthetic regression fixture")
            holdings, _ = normalize_provider_holdings("IE00BD4TXV59", rows, meta, decimal_comma=True)
            self.assertAlmostEqual(holdings[0]["weight"], .605)
            with tempfile.TemporaryDirectory() as directory:
                path = write_etf_output("IE00BD4TXV59", holdings, directory)
                self.assertEqual(path.name, "holdings_IE00BD4TXV59.json")
                self.assertEqual(read_json(path)[0]["isin"], "US0378331005")
                with self.assertRaises(ValueError):
                    write_etf_output("IE00B4L5Y983", holdings, directory)
                self.assertFalse((Path(directory) / "holdings.json").exists())
            with self.assertRaises(ValueError):
                read_provider_export(b"<!doctype html><html>not a CSV</html>")
            with self.assertRaises(ValueError):
                normalize_provider_holdings("IE00B4L5Y983", rows, meta, decimal_comma=True)

        def test_provider_domain_and_isin_guards(self):
            with self.assertRaises(ValueError):
                provider_url("https://ubs.com.evil.example/holdings.csv", "ubs")
            with self.assertRaises(ValueError):
                provider_url("https://www.ishares.com/holdings.csv", "ubs")
            provider_url("https://www.ubs.com/holdings.csv", "ubs")
            holdings, _ = demo_inputs()
            with self.assertRaises(ValueError):
                validate_isin(None)
            with self.assertRaises(ValueError):
                provider_holdings("IE00BD4TXV59", provider="ubs")

        def test_smi_isin_mapping_without_network(self):
            rows = [{"symbol": "AAPL", "security_isin": None},
                    {"symbol": "MSFT", "security_isin": "US5949181045"}]
            with patch(__name__ + ".fetch_ishares") as fetch:
                result = enrich_smi_isins(rows, isin_map={"AAPL": "US0378331005"})
                fetch.assert_not_called()
                self.assertEqual(result[0]["isin"], "US0378331005")
                self.assertEqual(result[1]["isin_status"], "resolved")

        def test_exclusion_before_network(self):
            yf = Mock()
            with self.assertRaises(ExcludedCandidate):
                fetch_security(yf, "WDAY-USD.SW", date(2025, 7, 1), date(2026, 6, 30),
                               date(2026, 9, 8), set(), {}, Path("unused"))
            yf.Ticker.assert_not_called()
            with self.assertRaises(ExcludedCandidate):
                check_candidate("FOREIGN.SW", {"country": "Germany"}, {}, require_metadata=True)
            with self.assertRaises(ValueError):
                check_candidate("NESN.SW", {}, {}, require_metadata=True)
            with self.assertRaises(ValueError):
                check_candidate("FOREIGN.SW", {"country": "Germany"}, {}, incumbent=True)
            check_candidate("FOREIGN.SW", {"country": "Germany", "currency": "CHF"},
                            {"eligible": True}, require_metadata=True)

        def test_missing_share_fallbacks(self):
            yf = Mock()
            ticker = yf.Ticker.return_value
            old = datetime(2026, 5, 1)
            future = datetime(2027, 1, 1)
            ticker.get_shares_full.return_value = SimpleNamespace(
                empty=False, items=lambda: [(old, 125000), (future, 999999)])
            shares, source = resolve_shares(yf, "TEST.SW", {}, {}, date(2026, 9, 8))
            self.assertEqual(shares, 125000)
            self.assertIn("2026-05-01", source)
            ticker.get_shares_full.return_value = None
            ticker.get_fast_info.return_value = {"shares": 130000}
            self.assertEqual(resolve_shares(yf, "TEST.SW", {}, {}, date(2026, 9, 8))[0], 130000)
            ticker.get_fast_info.return_value = {"shares": None}
            info = {"currency": "CHF", "marketCap": 14000000, "regularMarketPrice": 100}
            self.assertEqual(resolve_shares(yf, "TEST.SW", info, {}, date(2026, 9, 8))[0], 140000)
            with self.assertRaises(ValueError):
                resolve_shares(yf, "ROG.SW", info, {}, date(2026, 9, 8))
            with self.assertRaises(ValueError):
                resolve_shares(yf, "WAF.SW", {}, {}, date(2026, 9, 8))
            with self.assertRaises(ValueError):
                resolve_shares(yf, "TEST.SW", info, {"shares_outstanding": 0}, date(2026, 9, 8))

        def test_metadata_filter_precedes_history(self):
            try:
                import pandas
            except ImportError:
                self.skipTest("Install pandas for the quote-cache adapter regression")
            yf = Mock()
            yf.Ticker.return_value.get_info.return_value = {"country": "Germany", "currency": "CHF"}
            callback = lambda info: check_candidate("FOREIGN.SW", info, {}, require_metadata=True)
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ExcludedCandidate):
                    quote_inputs(yf, "FOREIGN.SW", date(2025, 7, 1), date(2026, 9, 8),
                                 Path(directory), eligibility_check=callback)
                yf.Ticker.return_value.history.assert_not_called()
                # Existing v1 cache must also pass the new filter.
                cache = Path(directory) / "FOREIGN.SW_2025-07-01_2026-09-08.json"
                cache.write_text(json.dumps({"info": {"country": "Germany"}, "history": [
                    {"Date": "2026-09-08", "Close": 10, "Volume": 100}]}))
                yf.reset_mock()
                with self.assertRaises(ExcludedCandidate):
                    quote_inputs(yf, "FOREIGN.SW", date(2025, 7, 1), date(2026, 9, 8),
                                 Path(directory), eligibility_check=callback)
                yf.Ticker.assert_not_called()

        def test_run_diagnostics_not_repeated_on_holdings(self):
            rows, _ = demo_inputs()
            lookup = {s.symbol: s for s in rows[:20]}
            symbols = list(lookup) + ["WDAY-USD.SW", "BROKEN.SW"]
            def fake_fetch(yf, symbol, *args):
                if symbol == "WDAY-USD.SW":
                    raise ExcludedCandidate("currency trading line")
                if symbol == "BROKEN.SW":
                    raise ValueError("missing price fixture")
                return lookup[symbol]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "diagnostics.json"
                with patch.dict(sys.modules, {"yfinance": ModuleType("yfinance")}), \
                     patch(__name__ + ".fetch_security", side_effect=fake_fetch):
                    with self.assertLogs(LOG, level="WARNING"):
                        loaded, meta = live_inputs(universe=symbols, incumbents=set(lookup),
                                    allow_incomplete=True, diagnostics_path=path)
                    self.assertEqual(read_json(path)["excluded_count"], 1)
                    self.assertEqual(read_json(path)["failed_count"], 1)
                    holdings = build_holdings("CH0008899764", loaded, meta)
                    self.assertEqual(len(holdings), 20)
                    self.assertNotIn("BROKEN.SW", json.dumps(holdings))
                    with self.assertLogs(LOG, level="WARNING"), self.assertRaises(RuntimeError):
                        live_inputs(universe=symbols, incumbents=set(lookup), diagnostics_path=path)

        def test_caps(self):
            rng = random.Random(7)
            for n in (6, 20, 50):
                for _ in range(50):
                    caps = {str(i): 10 ** rng.uniform(-3, 12) for i in range(n)}
                    weights = capped_weights(caps)
                    self.assertAlmostEqual(sum(weights.values()), 1)
                    self.assertLessEqual(max(weights.values()), 0.18 + 1e-10)
                    uncapped = [k for k, w in weights.items() if w < 0.18 - 1e-10]
                    if len(uncapped) > 1:
                        a, b = uncapped[:2]
                        self.assertAlmostEqual((weights[a] / weights[b]) / (caps[a] / caps[b]), 1)
            with self.assertRaises(ValueError):
                capped_weights({str(i): 1 for i in range(5)})
            with self.assertRaises(ValueError):
                capped_weights({"a": float("nan")})

        def test_buffer_and_score(self):
            rows, meta = demo_inputs()
            selected, scores = select_components(rows)
            symbols = {s.symbol for s in selected}
            self.assertEqual(len(selected), 20)
            self.assertIn("DEMO22.SW", symbols)
            self.assertNotIn("DEMO19.SW", symbols)
            total = sum(s.avg_ff_cap_chf for s in rows)
            self.assertAlmostEqual(scores[rows[0].symbol]["selection_score"], rows[0].avg_ff_cap_chf / total)
            # A dominant turnover observation must change the blended ranking.
            rows[-1].turnover_chf = 1e18
            _, scores = select_components(rows)
            self.assertEqual(scores[rows[-1].symbol]["selection_rank"], 1)

        def test_issuer_cap(self):
            rows, meta = demo_inputs()
            rows[1].issuer_id = rows[0].issuer_id
            out = build_holdings("CH0008899764", rows, meta)
            combined = sum(h["weight"] for h in out if h["issuer_id"] == rows[0].issuer_id)
            self.assertAlmostEqual(combined, 0.18)
            self.assertAlmostEqual(sum(h["weight"] for h in out), 1)
            self.assertEqual(len(out), 20)
            json.dumps(out, allow_nan=False)

        def test_dual_primary(self):
            rows, _ = demo_inputs()
            rows[0].multiple_primary = True
            rows[0].six_turnover_share = 0.4
            rows[0].primary_turnover_chf = 0
            selected, _ = select_components(rows)
            self.assertNotIn(rows[0], selected)
            rows[0].primary_turnover_chf = 1e18
            selected, _ = select_components(rows)
            self.assertIn(rows[0], selected)

        def test_identifiers_and_snapshot(self):
            self.assertEqual(validate_isin("ch0008899764"), "CH0008899764")
            with self.assertRaises(ValueError):
                validate_isin("CH0008899765")
            with self.assertRaises(ValueError):
                resolve_etf("US0378331005")
            rows, meta = demo_inputs()
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "snapshot.json"
                save_snapshot(path, rows, meta)
                out = presumed_smi_holdings("CH0008899764", snapshot=path)
                self.assertEqual(len(out), 20)
                self.assertEqual(out[0]["estimate_type"], "synthetic_demo")
            rows.append(rows[0])
            with self.assertRaises(ValueError):
                select_components(rows)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():
        raise SystemExit(1)


class ProviderPage(HTMLParser):
    """Parse only fund components, never collateral/security-lending tables."""
    def __init__(self):
        super().__init__()
        self.components = {}

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag != "walrus-render-on-client" or "componentprops" not in data:
            return
        try:
            props = json.loads(data["componentprops"])
        except ValueError:
            return
        component = props.get("componentId")
        if component and ("containersByNameMap" in props or "apiHost" in props):
            self.components[component] = props


def provider_url(url: str, provider: str) -> str:
    """Only public HTTPS URLs on the requested provider's domains."""
    parsed = urlparse(url)
    domains = ("ishares.com", "blackrock.com") if provider == "ishares" else ("ubs.com",)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or not any(
            host == domain or host.endswith("." + domain) for domain in domains):
        raise ValueError(f"Expected an HTTPS {provider} URL on {', '.join(domains)}")
    return url


def download_provider(url: str, provider: str, cache_dir: str | Path) -> bytes:
    """Short-lived cache, bounded requests and response size, checked redirects."""
    import hashlib
    from urllib.request import HTTPRedirectHandler, build_opener
    from urllib.error import HTTPError
    provider_url(url, provider)
    class CheckedRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            provider_url(newurl, provider)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    path = Path(cache_dir) / ("provider_" + hashlib.sha256(url.encode()).hexdigest() + ".bin")
    if path.exists() and time.time() - path.stat().st_mtime < 21600:
        return path.read_bytes()
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/csv,text/html",
                                    "x-application-id": "pp-ui-csr"})
    try:
        with build_opener(CheckedRedirect()).open(request, timeout=35) as response:
            data = response.read(30_000_001)
    except HTTPError as exc:
        raise RuntimeError(f"{provider} download returned HTTP {exc.code}; use an accessible full-holdings export.") from exc
    if len(data) > 30_000_000:
        raise ValueError("Provider response exceeds 30 MB")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    return data


def date_text(value: Any) -> str:
    text = str(value).strip().replace("Sept", "Sep")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%b/%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            result = datetime.strptime(text, fmt).date()
            if result > datetime.now(timezone.utc).date():
                raise ValueError("Holdings date is in the future")
            return result.isoformat()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized holdings date {value!r}; supply --as-of YYYY-MM-DD")


def fetch_ishares(etf_isin: str, *, product_url: str | None = None,
                  cache_dir: str | Path = ".smi_cache") -> tuple[list[dict], dict]:
    """Verified ISIN -> product page -> current public JSON holdings endpoint.

    The endpoint/context are read from the product page, not guessed from a
    ticker or a fixed product ID. Exact ISIN verification precedes holdings.
    Source mechanism inspected on 2026-09-10; schema changes fail explicitly.
    """
    etf_isin = validate_isin(etf_isin)
    if product_url is None:
        url = "https://www.ishares.com/varnish-api/core-search/search/products?" + urlencode({
            "site": "ishares-uk", "locale": "en-gb", "rows": 20, "start": 0,
            "userType": "individual", "query": etf_isin})
        search = json.loads(download_provider(url, "ishares", cache_dir))
        candidates = search.get("results", [])
        if len(candidates) != 1 or not str(candidates[0].get("portfolioId", "")).isdigit():
            raise ValueError("iShares ISIN search did not identify one product. Supply its --product-url; "
                             "the page's ETF ISIN will be verified before use.")
        product_url = "https://www.ishares.com/uk/individual/en/products/" + str(candidates[0]["portfolioId"])
    page = ProviderPage()
    page.feed(download_provider(product_url, "ishares", cache_dir).decode("utf-8-sig"))
    facts_component = page.components.get("keyFundFacts", {})
    facts = {}
    for container in facts_component.get("containersByNameMap", {}).values():
        facts.update({key: point.get("value") for key, point in container.get("dataPointsByNameMap", {}).items()})
    if facts.get("isin") != etf_isin:
        raise ValueError(f"Product-page ETF ISIN is {facts.get('isin')!r}, expected {etf_isin}. "
                         "Use the correct share-class URL, or an explicitly supplied holdings export.")
    component = page.components.get("holdings", {})
    context = component.get("context", {})
    host = component.get("apiHost")
    as_of = component.get("initAsOfDates", {}).get("all")
    required = ("productId", "appSubType", "targetSite", "locale", "userType")
    if not host or not as_of or any(not context.get(k) for k in required):
        raise ValueError("iShares page lacks the current full-holdings API context. Use --holdings-file.")
    query = {"appType": "PRODUCT_PAGE", "appSubType": context["appSubType"],
             "component": "holdings.all", "locale": context["locale"],
             "portfolioId": context["productId"], "targetSite": context["targetSite"],
             "userType": context["userType"], "excludeContent": "true",
             "asOfDate": as_of, "includeConfig": "true"}
    api_url = host.split("?", 1)[0] + "?" + urlencode(query)
    payload = json.loads(download_provider(api_url, "ishares", cache_dir))
    if str(payload.get("productId")) != str(context["productId"]):
        raise ValueError("Holdings API returned another product")
    try:
        points = payload["componentsByNameMap"]["holdings"]["containersByNameMap"]["all"]["dataPointsByNameMap"]
        columns = {key: point["value"] for key, point in points.items() if isinstance(point.get("value"), list)}
        size = len(columns["issueName"])
        needed = ("issueName", "assetClass", "holdingPercent", "isin", "ticker", "exchange")
        if any(len(columns.get(k, [])) != size for k in needed):
            raise ValueError("Misaligned or missing holdings columns")
        rows = [{key: values[i] for key, values in columns.items() if len(values) == size} for i in range(size)]
        observed_date = date_text(points["asOfDate"]["value"])
        if observed_date != date_text(as_of):
            raise ValueError("Holdings API returned a different valuation date")
    except (KeyError, TypeError) as exc:
        raise ValueError("Unsupported iShares holdings response schema") from exc
    return rows, {"etf_isin": etf_isin, "etf_name": payload.get("fundName", etf_isin),
                  "benchmark": facts.get("indexSeriesName"), "provider": "ishares",
                  "as_of": observed_date, "source": api_url, "product_url": product_url,
                  "product_structure": facts.get("productStructure"),
                  "replication": facts.get("fundMethodologyTypeCode"),
                  "source_binding": "ETF ISIN verified on issuer product page"}


def field_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower().replace("ä", "a").replace("ö", "o").replace("ü", "u"))


PROVIDER_FIELDS = {
    "name": ("name", "issuename", "securityname", "securitydescription", "bezeichnung", "instrumentname", "titel"),
    "isin": ("isin", "securityisin", "instrumentisin", "isincode"),
    "symbol": ("ticker", "symbol"),
    "weight": ("holdingpercent", "weight", "weighting", "gewichtung", "gewicht", "portfolioanteil", "weightpercentage",
               "portfolioweight", "fundweight", "weightin", "gewichtungin", "percentageofnetassets"),
    "asset_class": ("assetclass", "assettype", "anlageklasse", "anlagekategorie"),
    "exchange": ("exchange", "borse", "stockexchange"),
    "currency": ("marketcurrencycode", "marketcurrency", "currency", "wahrung"),
}


def row_field(row: dict, name: str):
    lookup = {field_key(k): v for k, v in row.items()}
    return next((lookup[key] for key in PROVIDER_FIELDS[name] if key in lookup), None)


def read_provider_export(data: bytes) -> tuple[list[dict], dict]:
    """Read full CSV/JSON exports; do not confuse HTML pages with holdings."""
    text = data.decode("utf-8-sig")
    if text.lstrip().startswith("<"):
        raise ValueError("Download contains HTML, not a holdings export. Use a direct CSV/JSON URL or --holdings-file.")
    if text.lstrip().startswith(("{", "[")):
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj, {}
        if not isinstance(obj.get("holdings"), list):
            raise ValueError("JSON must contain a holdings array")
        return obj["holdings"], {k: v for k, v in obj.items() if k != "holdings"}
    for delimiter in (",", ";", "\t"):
        lines = list(csv.reader(StringIO(text), delimiter=delimiter))
        metadata = {}
        for i, line in enumerate(lines[:100]):
            if len(line) >= 2:
                label = field_key(line[0])
                if label in ("fundholdingsasof", "asof", "date", "datum", "stichtag"):
                    metadata["as_of"] = line[1]
                if label in ("etfisin", "fundisin", "fondsisin"):
                    metadata["etf_isin"] = line[1].strip()
            header = {field_key(k) for k in line}
            if (header.intersection(PROVIDER_FIELDS["name"]) and header.intersection(PROVIDER_FIELDS["weight"])
                    and header.intersection(PROVIDER_FIELDS["isin"] + PROVIDER_FIELDS["symbol"])):
                records = []
                for values in lines[i + 1:]:
                    if not values or all(not v.strip() for v in values):
                        continue
                    if len(values) != len(line):
                        # Typical trailing legal text is a single field.
                        if len(values) == 1:
                            continue
                        raise ValueError("Malformed holdings CSV row")
                    records.append(dict(zip(line, values)))
                if not records:
                    raise ValueError("Holdings export has no records")
                return records, metadata
    raise ValueError("No supported holdings header. Expected Name, ISIN/Ticker, Weight (%), and Asset Class.")


def provider_number(value: Any, decimal_comma: bool = False) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing numeric weight")
    text = str(value).strip().replace("%", "").replace("\u00a0", "").replace(" ", "").replace("'", "").replace("’", "")
    text = text.replace(".", "").replace(",", ".") if decimal_comma else text.replace(",", "")
    number = float(text)
    if not math.isfinite(number) or number < 0:
        raise ValueError("Equity weights must be finite and nonnegative")
    return number


def normalize_provider_holdings(etf_isin: str, rows: list[dict], metadata: dict, *,
        isin_map: dict | None = None, allow_missing_isins: bool = False,
        equities_only: bool = False, weight_unit: str = "percent", decimal_comma: bool = False,
        allow_partial: bool = False) -> tuple[list[dict], dict]:
    etf_isin = validate_isin(etf_isin)
    if metadata.get("etf_isin") and metadata["etf_isin"] != etf_isin:
        raise ValueError("Export ETF ISIN differs from the requested ETF")
    as_of = date_text(metadata.get("as_of", ""))
    if weight_unit not in ("percent", "fraction"):
        raise ValueError("weight_unit must be percent or fraction")
    output, excluded, missing = [], [], []
    mapping = isin_map or {}
    if not isinstance(mapping, dict):
        raise ValueError("ISIN map must be an object")
    mapping = {key: validate_isin(value) for key, value in mapping.items()}
    equity_labels = {"equity", "equities", "stock", "stocks", "aktien", "aktie"}
    nonequity_labels = {"cash", "cashcollateral", "cashcollateralandmargins", "cashandorderivatives", "cashandderivatives", "money market",
                        "moneymarket", "futures", "future", "fx", "forwards", "forward", "swaps", "swap",
                        "fixedincome", "bond", "bonds", "obligationen", "liquiditat", "geldmarkt", "derivatives"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Each holdings record must be an object")
        name = str(row_field(row, "name") or "").strip()
        asset = field_key(row_field(row, "asset_class") or "")
        if asset in nonequity_labels:
            excluded.append({"name": name, "reason": "non-equity position"})
            continue
        if asset not in equity_labels and not (not asset and equities_only):
            raise ValueError(f"Unrecognized/missing asset class for {name!r}; use --equities-only only for an equity-only export.")
        if not name:
            raise ValueError(f"Missing instrument name in row {index + 1}")
        symbol = str(row_field(row, "symbol") or "").strip()
        exchange = str(row_field(row, "exchange") or "").strip()
        key = f"{symbol}|{exchange}"
        raw_isin = mapping.get(key, row_field(row, "isin"))
        try:
            isin = validate_isin(str(raw_isin or ""))
            if isin == etf_isin:
                raise ValueError("ETF ISIN copied into constituent row")
        except ValueError:
            isin = None
            missing.append({"symbol": symbol, "exchange": exchange, "name": name, "lookup_key": key})
        weight = provider_number(row_field(row, "weight"), decimal_comma) / (100 if weight_unit == "percent" else 1)
        output.append({"etf_isin": etf_isin, "etf_name": metadata.get("etf_name", etf_isin),
            "provider": metadata["provider"], "benchmark": metadata.get("benchmark"),
            "symbol": symbol, "name": name, "isin": isin, "security_isin": isin,
            "isin_status": "resolved" if isin else "unresolved",
            "isin_source": "user mapping" if key in mapping else "provider holdings export",
            "exchange": exchange, "currency": row_field(row, "currency"),
            "reported_weight": weight, "weight": weight, "as_of": as_of,
            "estimate_type": "provider_reported_equity_basket", "index_constituent_status": "not_verified",
            "source": metadata["source"], "product_structure": metadata.get("product_structure"),
            "replication": metadata.get("replication"),
            "weight_basis": "Normalized included equities; reported_weight retains published NAV fraction"})
    total = math.fsum(h["reported_weight"] for h in output)
    if not output or total <= 0:
        raise ValueError("No positive-weight equity basket in the export")
    if total > 1.05 or (total < 0.8 and not allow_partial):
        raise ValueError(f"Reported equities sum to {total:.2%}. Check units and completeness; "
                         "--allow-partial explicitly permits an equity slice below 80%.")
    if missing and not allow_missing_isins:
        raise ValueError(f"{len(missing)} equity ISINs missing/invalid. Supply --isin-map entries keyed by ticker|exchange; "
                         f"examples: {json.dumps(missing[:5])}. No holdings file written.")
    seen = set()
    for holding in output:
        key = (holding["isin"], holding["symbol"], holding["exchange"])
        if key in seen:
            raise ValueError(f"Duplicate holdings row: {key}; consolidate the source explicitly")
        seen.add(key)
        holding["weight"] /= total
    output.sort(key=lambda h: (-h["weight"], h["name"], h["symbol"]))
    diagnostics = {"etf_isin": etf_isin, "provider": metadata["provider"], "source": metadata["source"],
                   "as_of": as_of, "source_binding": metadata.get("source_binding"),
                   "input_rows": len(rows), "equity_rows": len(output),
                   "reported_equity_weight": total, "normalized_equity_weight": math.fsum(h["weight"] for h in output),
                   "missing_isins": missing, "excluded_positions": excluded,
                   "limitations": ["Provider-reported equities are not verified index constituents.",
                                   "Cash and derivatives excluded; weights normalized within equity basket."]}
    return output, diagnostics


def provider_holdings(etf_isin: str, *, provider: str = "ishares", product_url: str | None = None,
        holdings_file: str | Path | None = None, holdings_url: str | None = None,
        as_of: str | None = None, benchmark: str | None = None, cache_dir: str | Path = ".smi_cache",
        **options) -> tuple[list[dict], dict]:
    provider = provider.lower()
    if provider not in ("ubs", "ishares"):
        raise ValueError("Supported providers: ubs, ishares")
    validate_isin(etf_isin)
    if sum(x is not None for x in (holdings_file, holdings_url, product_url)) > 1:
        raise ValueError("Choose one of --holdings-file, --holdings-url or --product-url")
    if holdings_file is not None or holdings_url is not None:
        data = Path(holdings_file).read_bytes() if holdings_file is not None else download_provider(holdings_url, provider, cache_dir)
        rows, metadata = read_provider_export(data)
        metadata.update({"provider": provider, "source": str(holdings_file or holdings_url),
                         "source_binding": "User-supplied full portfolio export for the requested ETF"})
    elif provider == "ishares":
        rows, metadata = fetch_ishares(etf_isin, product_url=product_url, cache_dir=cache_dir)
        # Live API weights are numeric percentages regardless of UI locale.
        if options.get("weight_unit", "percent") != "percent" or options.get("decimal_comma", False):
            raise ValueError("Live iShares uses numeric percentage weights; omit unit/decimal overrides")
    else:
        raise ValueError("UBS automatic download discovery is unavailable. Supply its full CSV/JSON "
                         "export with --holdings-file or a public UBS --holdings-url, plus --as-of if needed.")
    if as_of:
        if metadata.get("as_of") and date_text(metadata["as_of"]) != date_text(as_of):
            raise ValueError("Requested --as-of differs from the export's date")
        metadata["as_of"] = as_of
    if benchmark:
        if metadata.get("benchmark") and metadata["benchmark"].casefold() != benchmark.casefold():
            raise ValueError("Requested benchmark differs from provider metadata")
        metadata["benchmark"] = benchmark
    return normalize_provider_holdings(etf_isin, rows, metadata, **options)


def get_etf_holdings(etf_isin: str, **options) -> list[dict[str, Any]]:
    """Public API for UBS/iShares reported equity baskets across benchmarks."""
    return provider_holdings(etf_isin, **options)[0]


def enrich_smi_isins(holdings: list[dict], *, isin_map: dict | None = None,
                     allow_missing: bool = False, cache_dir: str | Path = ".smi_cache") -> list[dict]:
    """Resolve only selected instruments; never fill a class ISIN by fuzzy name."""
    mapping = isin_map or {}
    if not isinstance(mapping, dict):
        raise ValueError("ISIN map must be an object")
    mapping = {key: validate_isin(value) for key, value in mapping.items()}
    unresolved = []
    for h in holdings:
        candidate = mapping.get(h["symbol"], h.get("security_isin"))
        try:
            h["security_isin"] = validate_isin(str(candidate or ""))
            h["isin_source"] = "user mapping or input snapshot"
        except ValueError:
            unresolved.append(h)
    reference = {}
    if unresolved:
        try:
            rows, meta = fetch_ishares("IE00B4L5Y983", cache_dir=cache_dir)
            for row in rows:
                if row.get("exchange") in ("SIX Swiss Exchange", "Six Swiss Exchange"):
                    symbol = str(row.get("ticker", "")) + ".SW"
                    try:
                        isin = validate_isin(str(row.get("isin", "")))
                    except ValueError:
                        continue
                    reference.setdefault(symbol, set()).add(isin)
        except (ValueError, RuntimeError, OSError) as exc:
            LOG.warning("iShares ISIN reference unavailable: %s", exc)
    missing = []
    for h in unresolved:
        candidates = reference.get(h["symbol"], set())
        if len(candidates) == 1:
            h["security_isin"] = next(iter(candidates))
            h["isin_source"] = "iShares: exact SIX ticker; reference date " + meta["as_of"]
        else:
            try:
                import yfinance as yf
                h["security_isin"] = validate_isin(str(yf.Ticker(h["symbol"]).get_isin()))
                h["isin_source"] = "Yahoo ticker ISIN lookup"
            except Exception as exc:
                LOG.warning("ISIN unresolved for %s: %s", h["symbol"], type(exc).__name__)
                h["security_isin"] = None
                h["isin_source"] = None
                missing.append(h["symbol"])
    for h in holdings:
        h["isin"] = h["security_isin"]
        h["isin_status"] = "resolved" if h["isin"] else "unresolved"
    if missing and not allow_missing:
        raise ValueError("ISIN lookup failed for " + ", ".join(missing) + "; supply --isin-map. No holdings file written.")
    return holdings


def write_etf_output(etf_isin: str, holdings: list[dict], output_dir: str | Path = ".") -> Path:
    """Always include the ETF ISIN; atomically replace only its own output."""
    isin = validate_isin(etf_isin)
    if not holdings or any(h.get("etf_isin") != isin for h in holdings):
        raise ValueError("Output basket is empty or belongs to a different ETF")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"holdings_{isin}.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(holdings, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etf_isin", nargs="?")
    parser.add_argument("--mode", choices=("auto", "provider", "reconstruct"), default="auto")
    parser.add_argument("--provider", choices=("ubs", "ishares"))
    parser.add_argument("--product-url")
    parser.add_argument("--holdings-file", type=Path)
    parser.add_argument("--holdings-url")
    parser.add_argument("--as-of", help="Export valuation date, YYYY-MM-DD")
    parser.add_argument("--benchmark", help="Benchmark label for an explicit provider export")
    parser.add_argument("--weight-unit", choices=("percent", "fraction"), default="percent")
    parser.add_argument("--decimal-comma", action="store_true")
    parser.add_argument("--equities-only", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--isin-map", type=Path)
    parser.add_argument("--allow-missing-isins", action="store_true")
    parser.add_argument("--import-db", action="store_true",
                        help="Import provider holdings into PostgreSQL using DATABASE_URL instead of holdings JSON")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--stdout", action="store_true", help="Also emit the list on stdout")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--save-snapshot", type=Path)
    parser.add_argument("--universe", type=Path)
    parser.add_argument("--incumbents", type=Path)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--diagnostics", type=Path, help="Write live excluded/failed candidates once as JSON")
    parser.add_argument("--cache-dir", type=Path, default=Path(".smi_cache"))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Explicitly accept missing candidates and/or unknown incumbents")
    parser.add_argument("--assume-smi", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.self_test:
        self_test()
        return
    if not args.etf_isin:
        parser.error("Provide an ETF ISIN")
    args.etf_isin = args.etf_isin.strip().upper()
    provider_mode = args.mode == "provider" or (args.mode == "auto" and not args.demo and not args.snapshot
                     and (args.import_db or args.provider or args.product_url or args.holdings_file or args.holdings_url
                          or args.etf_isin not in ETF_REGISTRY))
    if args.import_db and not provider_mode:
        parser.error("--import-db requires provider mode; demo/reconstructed baskets cannot be imported")
    if args.import_db and not os.environ.get("DATABASE_URL"):
        parser.error("Set DATABASE_URL to the target PostgreSQL database before using --import-db")
    provider_options = (args.product_url or args.holdings_file or args.holdings_url or args.as_of
                        or args.benchmark or args.decimal_comma or args.equities_only or args.allow_partial
                        or args.weight_unit != "percent")
    if not provider_mode and provider_options:
        parser.error("Provider input options cannot be combined with reconstruction/demo/snapshot")
    if provider_mode and (args.snapshot or args.demo or args.universe or args.incumbents or args.overrides
                          or args.allow_incomplete or args.assume_smi or args.save_snapshot):
        parser.error("SMI input options cannot be combined with provider mode")
    if args.snapshot and args.demo:
        parser.error("Choose snapshot or demo, not both")
    if (args.snapshot or args.demo) and (args.universe or args.incumbents or args.overrides or args.allow_incomplete or args.diagnostics):
        parser.error("Live input options cannot be combined with snapshot/demo")
    try:
        args.etf_isin = validate_isin(args.etf_isin)
        mapping = read_json(args.isin_map) if args.isin_map else {}
        if not isinstance(mapping, dict):
            raise ValueError("ISIN map must be a JSON object")
        # Invalid user overrides are always errors, even if missing IDs are allowed.
        mapping = {key: validate_isin(value) for key, value in mapping.items()}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        diagnostic_path = args.diagnostics or args.output_dir / f"diagnostics_{args.etf_isin}.json"
        if provider_mode:
            result, diagnostics = provider_holdings(args.etf_isin, provider=args.provider or "ishares",
                product_url=args.product_url, holdings_file=args.holdings_file, holdings_url=args.holdings_url,
                as_of=args.as_of, benchmark=args.benchmark, cache_dir=args.cache_dir, isin_map=mapping,
                allow_missing_isins=args.allow_missing_isins, weight_unit=args.weight_unit,
                decimal_comma=args.decimal_comma, equities_only=args.equities_only, allow_partial=args.allow_partial)
            diagnostic_path.write_text(json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
        elif args.demo:
            rows, meta = demo_inputs()
            result = build_holdings(args.etf_isin, rows, meta, args.assume_smi)
            if args.save_snapshot:
                save_snapshot(args.save_snapshot, rows, meta)
        elif args.snapshot:
            result = presumed_smi_holdings(args.etf_isin, snapshot=args.snapshot,
                         assume_smi=args.assume_smi, save_inputs=args.save_snapshot,
                         isin_map=mapping, allow_missing_isins=args.allow_missing_isins)
        else:
            universe = read_json(args.universe) if args.universe else None
            incumbents = read_json(args.incumbents) if args.incumbents else None
            for label, values in (("universe", universe), ("incumbents", incumbents)):
                if values is not None and (not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values)):
                    raise ValueError(f"{label} must be an array of unique symbol strings")
            result = presumed_smi_holdings(args.etf_isin, assume_smi=args.assume_smi,
                         save_inputs=args.save_snapshot, universe=universe,
                         incumbents=set(incumbents) if incumbents is not None else None,
                         overrides=read_json(args.overrides) if args.overrides else None,
                         allow_incomplete=args.allow_incomplete, cache_dir=args.cache_dir, workers=args.workers,
                         diagnostics_path=diagnostic_path, isin_map=mapping,
                         allow_missing_isins=args.allow_missing_isins)
        if args.demo or args.snapshot:
            diagnostic_path.write_text(json.dumps({"etf_isin": args.etf_isin,
                "rows": len(result), "mode": "demo" if args.demo else "snapshot"}, indent=2), encoding="utf-8")
        if args.import_db:
            # Keep retrieval independent of SQLAlchemy; DB dependencies load only on request.
            from importlib import import_module
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
            db_import = import_module("app.services.holdings_db_import")
            imported = db_import.import_to_database(args.etf_isin, result)
            LOG.info("Imported %d holdings for %s on %s (replaced %d)",
                     imported["imported"], imported["isin"], imported["as_of"], imported["replaced"])
        else:
            path = write_etf_output(args.etf_isin, result, args.output_dir)
            LOG.info("Wrote %d instruments to %s", len(result), path)
        LOG.info("Diagnostics: %s", diagnostic_path)
        if args.stdout:
            print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, TypeError, RuntimeError, OSError, ArithmeticError) as exc:
        LOG.error("%s", exc)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
