"""
import_provider_metadata.py — bulk-import ETF metadata from UBS and iShares
provider exports (no full holdings, no license needed).

Sources:
    UBS  "UBS ETF Product Overview CH EN.xlsx"   (real .xlsx, header on row 5)
    iShares "iShares-Switzerland.xls"            (actually SpreadsheetML/XML, German-localized)

Upserts into the `etfs` table by ISIN. Existing values are only filled in
when currently empty — this script never overwrites data already populated
by a more authoritative source (e.g. a parsed factsheet PDF). Conflicts are
logged, not silently overwritten.

Usage:
    set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/etfdata
    python import_provider_metadata.py --ubs "UBS ETF Product Overview CH EN.xlsx" --ishares "iShares-Switzerland.xls"
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from app.schemas import ETF

# ---------------------------------------------------------------------------
# Normalization tables
# ---------------------------------------------------------------------------
_DOMICILE_TO_ISO2 = {
    "ireland": "IE", "irland": "IE",
    "luxembourg": "LU", "luxemburg": "LU",
    "switzerland": "CH", "schweiz": "CH",
    "germany": "DE", "deutschland": "DE",
    "france": "FR", "frankreich": "FR",
    "united states": "US", "usa": "US", "vereinigte staaten von amerika": "US",
    "netherlands": "NL", "niederlande": "NL",
    "united kingdom": "GB", "vereinigtes königreich": "GB",
    "jersey": "JE", "guernsey": "GG",
}

_ASSET_CLASS_TO_EN = {
    "aktien": "Equities", "renten": "Bonds", "anleihen": "Bonds",
    "immobilien": "Real Estate", "rohstoffe": "Commodities",
    "geldmarkt": "Money Market", "edelmetalle": "Precious Metals",
}

_DIST_POLICY_MAP = {
    "yes": "Distributing", "no": "Accumulating",
    "ausschüttend": "Distributing", "thesaurierend": "Accumulating",
}

_REPLICATION_MAP = {
    "physical (full replicated)": "Physical (Full replication)",
    "synthetic (fully funded + total return swap)": "Synthetic",
    "replikation": "Physical (Full replication)",
    "optimierung": "Physical (Sampling)",
}


def _norm(s) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s if s and s.lower() != "nan" and s != "-" else None


def _map_lookup(table: dict, raw: Optional[str]) -> Optional[str]:
    """Map a raw provider value via a lookup table; fall back to the raw value
    (rather than dropping it) so unmapped values are still visible for review."""
    raw = _norm(raw)
    if raw is None:
        return None
    return table.get(raw.lower(), raw)


def _values_equal(a, b) -> bool:
    """Compare field values loosely so re-running an import doesn't report false
    conflicts from formatting differences (e.g. Decimal('0.200') vs float 0.2)."""
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return float(a) == float(b)
    return str(a) == str(b)


def _set_if_empty(etf: ETF, field: str, new_value, source_label: str, log: list):
    if new_value is None or new_value == "":
        return
    current = getattr(etf, field)
    if current is None or current == "":
        setattr(etf, field, new_value)
    elif not _values_equal(current, new_value):
        log.append(f"  [conflict] {etf.isin} {field}: keeping '{current}', {source_label} had '{new_value}'")


# ---------------------------------------------------------------------------
# UBS parser
# ---------------------------------------------------------------------------
def _to_int(value) -> Optional[int]:
    try:
        return int(value) if pd.notna(value) else None
    except (ValueError, TypeError):
        return None


def _to_float(value) -> Optional[float]:
    try:
        return float(value) if pd.notna(value) else None
    except (ValueError, TypeError):
        return None


def parse_ubs(path: str) -> list[dict]:
    df = pd.read_excel(path, sheet_name="Products", header=4)
    rows = []
    for _, r in df.iterrows():
        isin = _norm(r.get("ISIN"))
        if not isin:
            continue
        inception = None
        raw_date = _norm(r.get("Inception Date"))
        if raw_date:
            try:
                inception = datetime.strptime(raw_date, "%d.%m.%Y").date()
            except ValueError:
                pass
        rows.append({
            "isin": isin,
            "name": _norm(r.get("Share Class Name")),
            "provider": "UBS",
            "domicile": _map_lookup(_DOMICILE_TO_ISO2, r.get("Product Domicile")) if _norm(r.get("Product Domicile")) and len(_norm(r.get("Product Domicile"))) > 2 else _norm(r.get("Product Domicile")),
            "ter": _to_float(r.get("Total Expense Ratio (TER) (%)")),
            "fund_size": int(_to_float(r.get("AuM (Mn)")) * 1_000_000) if _to_float(r.get("AuM (Mn)")) is not None else None,
            "benchmark": _norm(r.get("Index Name")),
            "currency": _norm(r.get("Fund Currency")),
            "dividend_policy": _map_lookup(_DIST_POLICY_MAP, r.get("Distributions")),
            "replication_method": _map_lookup(_REPLICATION_MAP, r.get("Replication Type")),
            "asset_class": _norm(r.get("Asset Class")),
            "sfdr_classification": _norm(r.get("SFDR Classification")),
            "inception_date": inception,
            "wkn": _norm(r.get("WKN")),
            "num_constituents": _to_int(r.get("Number of index Constituents")),
        })
    return rows


# ---------------------------------------------------------------------------
# iShares parser (SpreadsheetML/XML, despite the .xls extension)
# ---------------------------------------------------------------------------
_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}


def _parse_xml_row(row) -> list:
    cells, idx = [], 0
    for cell in row.findall("ss:Cell", _NS):
        idx_attr = cell.get("{urn:schemas-microsoft-com:office:spreadsheet}Index")
        if idx_attr:
            idx = int(idx_attr) - 1
        while len(cells) < idx:
            cells.append(None)
        data = cell.find("ss:Data", _NS)
        cells.append(data.text if data is not None else None)
        idx += 1
    return cells


def _find_col(headers: list[str], keyword: str, limit: int = 32) -> Optional[int]:
    keyword = keyword.lower().replace(" ", "")
    for i, h in enumerate(headers[:limit]):
        if h and keyword in h.lower().replace("\n", "").replace(" ", ""):
            return i
    return None


def parse_ishares(path: str) -> list[dict]:
    tree = ET.parse(path)
    ws = tree.getroot().findall("ss:Worksheet", _NS)[0]
    data_rows = ws.find("ss:Table", _NS).findall("ss:Row", _NS)
    header = _parse_xml_row(data_rows[0])
    sub_header = _parse_xml_row(data_rows[1])

    col = {
        "name": _find_col(header, "Name"),
        "isin": _find_col(header, "ISIN"),
        "dist": _find_col(header, "Ertrags"),
        "currency": _find_col(header, "Währung"),
        "aum": _find_col(header, "AUM"),
        "domicile": _find_col(header, "Domizil"),
        "ter": _find_col(header, "Gesamtkostenquote"),
        "asset_class": _find_col(header, "Anlageklasse"),
        "inception": _find_col(header, "Auflagedatum"),
        "replication": _find_col(header, "Produktmethodik"),
        "benchmark": _find_col(header, "Referenzindex"),
        # SFDR classification lives in the trailing sustainability block, labeled in the sub-header row
        "sfdr": next((i for i, h in enumerate(sub_header) if h and "sfdr" in h.lower()), None),
    }

    rows = []
    for row in data_rows[2:]:
        cells = _parse_xml_row(row)
        if len(cells) <= max(v for v in col.values() if v is not None):
            cells += [None] * (max(col.values()) + 1 - len(cells))

        isin = _norm(cells[col["isin"]]) if col["isin"] is not None else None
        if not isin:
            continue

        inception = None
        raw_date = _norm(cells[col["inception"]]) if col["inception"] is not None else None
        if raw_date:
            try:
                inception = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass

        raw_domicile = _norm(cells[col["domicile"]]) if col["domicile"] is not None else None
        raw_aum = _to_float(_norm(cells[col["aum"]])) if col["aum"] is not None else None
        raw_ter = _to_float(_norm(cells[col["ter"]])) if col["ter"] is not None else None

        rows.append({
            "isin": isin,
            "name": _norm(cells[col["name"]]) if col["name"] is not None else None,
            "provider": "iShares",
            "domicile": _map_lookup(_DOMICILE_TO_ISO2, raw_domicile),
            "ter": raw_ter,
            "fund_size": int(raw_aum * 1_000_000) if raw_aum is not None else None,
            "benchmark": _norm(cells[col["benchmark"]]) if col["benchmark"] is not None else None,
            "currency": _norm(cells[col["currency"]]) if col["currency"] is not None else None,
            "dividend_policy": _map_lookup(_DIST_POLICY_MAP, cells[col["dist"]] if col["dist"] is not None else None),
            "replication_method": _map_lookup(_REPLICATION_MAP, cells[col["replication"]] if col["replication"] is not None else None),
            "asset_class": _map_lookup(_ASSET_CLASS_TO_EN, cells[col["asset_class"]] if col["asset_class"] is not None else None),
            "sfdr_classification": _norm(cells[col["sfdr"]]) if col["sfdr"] is not None else None,
            "inception_date": inception,
            "wkn": None,
            "num_constituents": None,
        })
    return rows


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
def upsert(db, rows: list[dict], source_label: str) -> dict:
    created, updated, log = 0, 0, []
    for row in rows:
        etf = db.query(ETF).filter_by(isin=row["isin"]).first()
        if not etf:
            etf = ETF(isin=row["isin"], name=row["name"] or row["isin"], provider=row["provider"])
            db.add(etf)
            created += 1
        else:
            updated += 1
        for field in ("name", "provider", "domicile", "ter", "fund_size", "benchmark", "currency",
                      "dividend_policy", "replication_method", "asset_class", "sfdr_classification",
                      "inception_date", "wkn", "num_constituents"):
            _set_if_empty(etf, field, row.get(field), source_label, log)
        etf.data_source = source_label
    db.commit()
    return {"created": created, "updated": updated, "log": log}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ubs", default="UBS ETF Product Overview CH EN.xlsx")
    parser.add_argument("--ishares", default="iShares-Switzerland.xls")
    parser.add_argument("--db", default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/etfdata"))
    args = parser.parse_args()

    engine = create_engine(args.db, poolclass=NullPool, pool_pre_ping=True)
    db = sessionmaker(bind=engine)()

    if os.path.exists(args.ubs):
        rows = parse_ubs(args.ubs)
        result = upsert(db, rows, "UBS")
        print(f"UBS: {len(rows)} parsed, {result['created']} created, {result['updated']} updated")
        for line in result["log"][:50]:
            print(line)
    else:
        print(f"Skipping UBS — file not found: {args.ubs}")

    if os.path.exists(args.ishares):
        rows = parse_ishares(args.ishares)
        result = upsert(db, rows, "iShares")
        print(f"iShares: {len(rows)} parsed, {result['created']} created, {result['updated']} updated")
        for line in result["log"][:50]:
            print(line)
    else:
        print(f"Skipping iShares — file not found: {args.ishares}")

    db.close()


if __name__ == "__main__":
    main()
