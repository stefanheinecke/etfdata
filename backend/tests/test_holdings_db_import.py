"""Offline tests: run from repo root with unittest discover -s backend/tests."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from html import escape
from itertools import permutations
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.holdings_db_import import prepare_holdings, import_holdings, import_to_database
from astra import smi_reconstruction as script

ISIN = "IE00B4L5Y983"


def basket():
    return [{"etf_isin": ISIN, "as_of": "2026-09-08", "name": "Apple Inc",
             "isin": "US0378331005", "reported_weight": 0.95, "weight": 1.0,
             "estimate_type": "provider_reported_equity_basket"}]


class HoldingsImportTests(unittest.TestCase):
    def test_explicit_metadata_normalized_at_db_boundary(self):
        rows = [{**basket()[0], "country": " United States ", "sector": "Technology"}]
        original = deepcopy(rows)
        prepared = prepare_holdings(ISIN, rows)[1][0]
        self.assertEqual(prepared["country"], "US")
        self.assertEqual(prepared["sector"], "Information Technology")
        self.assertEqual(rows, original)

    def test_absent_and_unrecognized_classifications_remain_unknown(self):
        # Neither a recognizable company name, ISIN prefix nor exchange is evidence.
        for metadata in ({}, {"country": None, "sector": None},
                         {"country": "", "sector": "-"},
                         {"country": "Atlantis", "sector": "Unclassified"}):
            with self.subTest(metadata=metadata):
                row = {**basket()[0], "exchange": "NASDAQ", "currency": "USD", **metadata}
                prepared = prepare_holdings(ISIN, [row])[1][0]
                self.assertIsNone(prepared["country"])
                self.assertIsNone(prepared["sector"])

    def test_same_isin_classification_consensus_is_order_independent(self):
        base = {**basket()[0], "reported_weight": 0.2}
        rows = [{**base, "country": "United States", "sector": "Technology"},
                {**base, "isin": " us0378331005 ", "country": "us",
                 "sector": "Information Technology"}, base]
        for ordering in permutations(rows):
            prepared = prepare_holdings(ISIN, list(ordering))[1]
            self.assertEqual(len(prepared), 1)
            self.assertEqual(prepared[0]["country"], "US")
            self.assertEqual(prepared[0]["sector"], "Information Technology")
            self.assertEqual(prepared[0]["weight"], Decimal("60"))

    def test_same_isin_conflicts_remain_unknown_in_any_order(self):
        base = {**basket()[0], "reported_weight": 0.2,
                "country": "US", "sector": "Technology"}
        for change, expected in (({"country": "Canada"}, (None, "Information Technology")),
                                 ({"sector": "Financials"}, ("US", None)),
                                 ({"country": "CA", "sector": "Financials"}, (None, None))):
            # A later repeated value or missing value must not erase a conflict.
            rows = [base, {**base, **change}, deepcopy(base),
                    {**base, "country": None, "sector": None}]
            for ordering in permutations(rows):
                with self.subTest(change=change, ordering=ordering):
                    prepared = prepare_holdings(ISIN, list(ordering))[1][0]
                    self.assertEqual((prepared["country"], prepared["sector"]), expected)
                    self.assertEqual(prepared["weight"], Decimal("80"))

    def test_classifications_do_not_leak_between_distinct_or_missing_isins(self):
        for first, second in (("US0378331005", "US5949181045"), (None, None)):
            base = {**basket()[0], "reported_weight": 0.4}
            prepared = prepare_holdings(ISIN, [
                {**base, "isin": first, "country": "US", "sector": "Technology"},
                {**base, "isin": second, "country": "CH", "sector": "Health Care"}])[1]
            self.assertEqual([(r["country"], r["sector"]) for r in prepared],
                             [("US", "Information Technology"), ("CH", "Health Care")])

    def test_nav_percent_not_normalized_equity_weight(self):
        as_of, rows = prepare_holdings(ISIN, basket())
        self.assertEqual(as_of, date(2026, 9, 8))
        self.assertEqual(rows[0]["weight"], Decimal("95"))

    def test_merge_same_security_multiple_listings(self):
        rows = basket()
        rows[0]["reported_weight"] = 0.4
        rows.append(deepcopy(rows[0]))
        self.assertEqual(prepare_holdings(ISIN, rows)[1][0]["weight"], Decimal("80"))

    def test_same_name_different_isins_are_separate(self):
        rows = basket()
        rows[0]["name"] = "EQT"
        rows[0]["reported_weight"] = 0.4
        rows.append({**rows[0], "isin": "US5949181045"})
        prepared = prepare_holdings(ISIN, rows)[1]
        self.assertEqual(len(prepared), 2)
        self.assertEqual([row["instrument_name"] for row in prepared], ["EQT", "EQT"])
        self.assertEqual({row["instrument_isin"] for row in prepared}, {"US0378331005", "US5949181045"})

    def test_same_isin_different_names_are_combined(self):
        rows = basket()
        rows[0]["reported_weight"] = 0.4
        rows.append({**rows[0], "name": "APPLE", "isin": " us0378331005 "})
        prepared = prepare_holdings(ISIN, rows)[1]
        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared[0]["weight"], Decimal("80"))
        self.assertEqual(prepared[0]["instrument_isin"], "US0378331005")

    def test_same_name_missing_isins_are_not_combined(self):
        row = {**basket()[0], "isin": None, "reported_weight": 0.4}
        prepared = prepare_holdings(ISIN, [row, deepcopy(row)])[1]
        self.assertEqual(len(prepared), 2)
        self.assertTrue(all(item["instrument_isin"] is None for item in prepared))

    def test_reject_empty_and_wrong_identity(self):
        for rows in ([], [{**basket()[0], "etf_isin": "IE00B5BMR087"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                prepare_holdings(ISIN, rows)

    def test_reject_mixed_dates(self):
        rows = basket() + [{**basket()[0], "as_of": "2026-09-07"}]
        with self.assertRaisesRegex(ValueError, "same valuation date"):
            prepare_holdings(ISIN, rows)

    def test_reject_invalid_weights_and_demo(self):
        for changes in ({"reported_weight": float("nan")}, {"reported_weight": -0.1},
                        {"reported_weight": 1.1}, {"reported_weight": None},
                        {"estimate_type": "synthetic_demo"}, {"as_of": "2999-01-01"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                prepare_holdings(ISIN, [{**basket()[0], **changes}])

    def test_missing_isin_is_preserved(self):
        rows = [{**basket()[0], "isin": None}]
        self.assertIsNone(prepare_holdings(ISIN, rows)[1][0]["instrument_isin"])

    def test_writes_only_selected_etf_date(self):
        db = MagicMock()
        etf_model, holding_model = MagicMock(), MagicMock()
        etf_query, holding_query = MagicMock(), MagicMock()
        db.query.side_effect = [etf_query, holding_query]
        etf_query.filter_by.return_value.with_for_update.return_value.first.return_value = SimpleNamespace(id="etf-id")
        holding_query.filter_by.return_value.delete.return_value = 2
        with patch.dict(sys.modules, {"app.schemas": SimpleNamespace(ETF=etf_model, Holding=holding_model)}):
            result = import_holdings(db, ISIN, basket())
        etf_query.filter_by.assert_called_once_with(isin=ISIN)
        holding_query.filter_by.assert_called_once_with(etf_id="etf-id", date=date(2026, 9, 8))
        holding_model.assert_called_once_with(etf_id="etf-id", date=date(2026, 9, 8),
            instrument_isin="US0378331005", instrument_name="Apple Inc", weight=Decimal("95"),
            country=None, sector=None, currency=None)
        db.flush.assert_called_once()
        db.commit.assert_not_called()  # transaction belongs to caller
        self.assertEqual(result["replaced"], 2)

    def test_missing_etf_does_not_delete(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = None
        with patch.dict(sys.modules, {"app.schemas": SimpleNamespace(ETF=object(), Holding=object())}):
            with self.assertRaisesRegex(ValueError, "metadata first"):
                import_holdings(db, ISIN, basket())
        self.assertEqual(db.query.call_count, 1)
        db.add_all.assert_not_called()

    def test_explicit_database_required(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            import_to_database(ISIN, basket())

    def test_cli_import_uses_writer_not_json_export(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["smi_reconstruction.py", ISIN, "--provider", "ishares", "--import-db", "--output-dir", directory]
            with patch.object(sys, "argv", args), patch.dict("os.environ", {"DATABASE_URL": "postgresql://unused"}), \
                    patch.object(script, "provider_holdings", return_value=(basket(), {})), \
                    patch("app.services.holdings_db_import.import_to_database", return_value={
                        "isin": ISIN, "as_of": "2026-09-08", "imported": 1, "replaced": 0}) as writer, \
                    patch.object(script, "write_etf_output") as exporter:
                script.main()
                writer.assert_called_once_with(ISIN, basket())
                exporter.assert_not_called()
            self.assertFalse((Path(directory) / f"holdings_{ISIN}.json").exists())

    def test_default_cli_still_exports_json(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["smi_reconstruction.py", ISIN, "--provider", "ishares", "--output-dir", directory]
            with patch.object(sys, "argv", args), patch.object(script, "provider_holdings", return_value=(basket(), {})), \
                    patch("app.services.holdings_db_import.import_to_database") as writer:
                script.main()
                writer.assert_not_called()
            self.assertTrue((Path(directory) / f"holdings_{ISIN}.json").exists())


class ProviderClassificationTests(unittest.TestCase):
    def test_holding_currency_preserved_or_unknown_not_inferred(self):
        for raw, expected in ((" usd ", "USD"), ("CHF", "CHF"), (None, None), ("UNKNOWN", None)):
            with self.subTest(raw=raw):
                row = {**basket()[0], "currency": raw}
                self.assertEqual(prepare_holdings(ISIN, [row])[1][0]["currency"], expected)
        rows = [{**basket()[0], "reported_weight": .3, "currency": currency}
                for currency in ("USD", "CHF")]
        self.assertIsNone(prepare_holdings(ISIN, rows)[1][0]["currency"])

    def test_provider_communication_label_is_normalized_in_db(self):
        rows = [{"issueName": "Example equity", "isin": "US0378331005",
                 "holdingPercent": 95, "assetClass": "Equity",
                 "countryOfRisk": "United States", "sectorName": "Communication"}]
        meta = {"provider": "ishares", "source": "offline fixture", "as_of": "2026-09-08"}
        holdings, _ = script.normalize_provider_holdings(ISIN, rows, meta)
        self.assertEqual(holdings[0]["sector"], "Communication")
        prepared = prepare_holdings(ISIN, holdings)[1][0]
        self.assertEqual(prepared["country"], "US")
        self.assertEqual(prepared["sector"], "Communication Services")

    def test_ishares_fetch_normalize_prepare_preserves_optional_columns(self):
        # Shape/field names verified against both cached iShares holdings responses.
        facts = {"componentId": "keyFundFacts", "containersByNameMap": {
            "facts": {"dataPointsByNameMap": {"isin": {"value": ISIN}}}}}
        component = {"componentId": "holdings",
                     "apiHost": "https://www.blackrock.com/test-api",
                     "initAsOfDates": {"all": "20260908"},
                     "context": {"productId": "251882", "appSubType": "ISHARES",
                                 "targetSite": "ishares-uk", "locale": "en_GB",
                                 "userType": "individual"}}
        page = "".join('<walrus-render-on-client componentprops="' + escape(json.dumps(p))
                       + '"></walrus-render-on-client>' for p in (facts, component)).encode()
        for metadata in ({"countryOfRisk": "United States", "sectorName": "Information Technology"}, {}):
            with self.subTest(metadata=metadata):
                raw = {"issueName": "Apple Inc", "isin": "US0378331005", "ticker": "AAPL",
                       "exchange": "NASDAQ", "holdingPercent": 95, "assetClass": "Equity", "marketCurrencyCode": "USD",
                       **metadata}
                points = {k: {"value": [v]} for k, v in raw.items()}
                points["asOfDate"] = {"value": "20260908"}
                payload = {"productId": "251882", "componentsByNameMap": {"holdings": {
                    "containersByNameMap": {"all": {"dataPointsByNameMap": points}}}}}
                with patch.object(script, "download_provider", side_effect=[page, json.dumps(payload).encode()]) as download:
                    rows, meta = script.fetch_ishares(ISIN,
                        product_url="https://www.ishares.com/uk/individual/en/products/251882")
                self.assertEqual(download.call_count, 2)
                self.assertEqual(rows, [raw])
                holdings, _ = script.normalize_provider_holdings(ISIN, rows, meta)
                self.assertEqual(holdings[0]["country"], metadata.get("countryOfRisk"))
                self.assertEqual(holdings[0]["sector"], metadata.get("sectorName"))
                prepared = prepare_holdings(ISIN, holdings)[1][0]
                self.assertEqual(prepared["country"], "US" if metadata else None)
                self.assertEqual(prepared["sector"], "Information Technology" if metadata else None)
                self.assertEqual(prepared["currency"], "USD")
                self.assertEqual(prepared["weight"], Decimal("95"))

    def test_export_explicit_country_sector_aliases_preserve_raw_values(self):
        for country_key, sector_key in (("Country", "Sector"), ("Location", "Sector"),
                                        ("Land", "Sektor")):
            data = (f"Name,ISIN,Weight (%),Asset Class,{country_key},{sector_key}\n"
                    "Apple Inc,US0378331005,95,Equity,United States,Technology\n").encode()
            rows, meta = script.read_provider_export(data)
            meta.update(provider="ishares", source="offline fixture", as_of="2026-09-08")
            holdings, _ = script.normalize_provider_holdings(ISIN, rows, meta)
            self.assertEqual(holdings[0]["country"], "United States")
            self.assertEqual(holdings[0]["sector"], "Technology")
            prepared = prepare_holdings(ISIN, holdings)[1][0]
            self.assertEqual(prepared["country"], "US")
            self.assertEqual(prepared["sector"], "Information Technology")


if __name__ == "__main__":
    unittest.main()