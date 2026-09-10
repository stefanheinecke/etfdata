"""Import iShares equity holdings from an ETF CSV using the Admin import backend.

Requires DATABASE_URL. Each ETF/date replacement is an independent transaction.
Unsupported asset classes are skipped; no metadata or schema is created.
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from astra.smi_reconstruction import provider_holdings, validate_isin


def read_ishares(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"isin", "provider", "asset_class"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV must contain isin, provider and asset_class columns")
        etfs = {}
        for row in reader:
            if (row.get("provider") or "").strip().casefold() != "ishares":
                continue
            isin = validate_isin((row.get("isin") or "").strip().upper())
            etfs.setdefault(isin, {"isin": isin, "asset_class": (row.get("asset_class") or "").strip()})
        return list(etfs.values())


def supported(etf):
    return etf["asset_class"].casefold() in {"equities", "equity", "aktien", "real estate"}


def import_one(isin):
    from app.services.holdings_db_import import import_to_database

    holdings, _ = provider_holdings(isin, provider="ishares")
    return import_to_database(isin, holdings)


def run_batch(etfs, available_isins, report, importer=import_one):
    totals = {"imported": 0, "failed": 0, "skipped": 0, "holdings": 0}
    for position, etf in enumerate(etfs, 1):
        isin = etf["isin"]
        record = {**etf, "timestamp": datetime.now(timezone.utc).isoformat()}
        if not supported(etf):
            record.update(status="skipped", reason="Unsupported asset class: importer is equity-only")
        elif isin not in available_isins:
            record.update(status="skipped", reason="Not an existing iShares ETF in target database")
        else:
            print(f"[{position}/{len(etfs)}] Retrieving {isin}", flush=True)
            try:
                result = importer(isin)
                record.update(status="imported", **result)
                totals["holdings"] += result["imported"]
            except (ValueError, RuntimeError) as exc:
                # Provider validation errors and the DB writer's sanitized errors.
                # Redact the connection URL defensively; never print tracebacks.
                reason = str(exc)
                if os.environ.get("DATABASE_URL"):
                    reason = reason.replace(os.environ["DATABASE_URL"], "[database URL redacted]")
                record.update(status="failed", reason=reason)
            except Exception as exc:
                record.update(status="failed", reason=f"Unexpected {type(exc).__name__}; details suppressed")
        totals[record["status"]] += 1
        report.write(json.dumps(record, ensure_ascii=False) + "\n")
        report.flush()
        print(f"[{position}/{len(etfs)}] {isin}: {record['status']}"
              f" — {record.get('reason', str(record.get('imported', 0)) + ' holdings')}", flush=True)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, default=Path(__file__).with_name("all_etfs.csv"))
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV and count ETFs without network or DB access")
    parser.add_argument("--report", type=Path, help="New JSONL report (existing files are never overwritten)")
    args = parser.parse_args(argv)
    try:
        etfs = read_ishares(args.csv)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    eligible = sum(supported(etf) for etf in etfs)
    print(f"iShares ETFs: {len(etfs)}; eligible equity/real-estate ETFs: {eligible}; unsupported: {len(etfs) - eligible}", flush=True)
    if args.dry_run or not etfs:
        return 0
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL must be set privately in this terminal")

    # Verify connectivity and ETF identities before requesting provider data.
    os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
    try:
        from app.db.database import SessionLocal
        from app.schemas import ETF

        with SessionLocal() as db:
            available = {isin for isin, provider in db.query(ETF.isin, ETF.provider).all()
                         if (provider or "").strip().casefold() == "ishares"}
    except Exception as exc:
        print(f"Database preflight failed ({type(exc).__name__}); no imports started. Check connection and schema.", file=sys.stderr)
        return 1

    report_path = args.report or args.csv.with_name(
        f"ishares_import_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.jsonl")
    with report_path.open("x", encoding="utf-8") as report:
        print(f"Report: {report_path}", flush=True)
        totals = run_batch(etfs, available, report)
    print(json.dumps(totals), flush=True)
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())