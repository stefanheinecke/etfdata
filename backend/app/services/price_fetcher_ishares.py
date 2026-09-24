"""
price_fetcher_ishares.py — full daily NAV history straight from the issuer's
own iShares product page (astra/smi_reconstruction.py fetch_ishares_nav_history),
as a more reliable alternative to price_fetcher_yfinance.py for European UCITS
ETFs, where yfinance/OpenFIGI ticker resolution is often unreliable or missing.
Same provider-page mechanism already used in production for holdings import.
"""
from decimal import Decimal
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.schemas import Performance

# Root of the backend package (services -> app -> backend root), where the
# sibling astra/ folder with smi_reconstruction.py lives (see admin.py's
# _holdings_script(), which loads the same module for holdings import).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _smi_module():
    import importlib.util
    import sys
    if "smi_reconstruction" in sys.modules:
        return sys.modules["smi_reconstruction"]
    for candidate in (_BACKEND_ROOT / "astra", _BACKEND_ROOT.parent / "astra"):
        path = candidate / "smi_reconstruction.py"
        if path.exists():
            spec = importlib.util.spec_from_file_location("smi_reconstruction", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["smi_reconstruction"] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("smi_reconstruction.py not found (expected in astra/)")


def fetch_prices_ishares(etf_id, isin: str, db, product_url: str | None = None) -> dict:
    """Fetch the full since-inception NAV history from the iShares product page
    and upsert it into the Performance table. Stored as both close_price
    (consumed by the existing Performance chart and risk-metrics calculations)
    and nav (semantically correct field), same value in both columns."""
    script = _smi_module()
    try:
        rows, meta = script.fetch_ishares_nav_history(isin, product_url=product_url)
    except (ValueError, RuntimeError) as exc:
        return {"success": False, "price_count": 0, "currency": None,
                "message": str(exc), "error": str(exc)}

    currency = meta.get("currency") or "USD"
    count = 0
    for row in rows:
        nav = Decimal(str(row["nav"]))
        stmt = pg_insert(Performance).values(
            etf_id=etf_id, date=row["date"], close_price=nav, nav=nav, currency=currency,
        ).on_conflict_do_update(
            index_elements=["etf_id", "date"],
            set_={"close_price": nav, "nav": nav, "currency": currency},
        )
        db.execute(stmt)
        count += 1
    db.commit()
    return {
        "success": True, "price_count": count, "currency": currency,
        "message": f"Fetched {count} NAV observations from iShares "
                   f"({meta['first_date']} to {meta['last_date']})",
        "error": None,
    }
