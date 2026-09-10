"""Offline tests: run from repo root with unittest discover -s backend/tests."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
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
    def test_nav_percent_not_normalized_equity_weight(self):
        as_of, rows = prepare_holdings(ISIN, basket())
        self.assertEqual(as_of, date(2026, 9, 8))
        self.assertEqual(rows[0]["weight"], Decimal("95"))

    def test_merge_same_security_multiple_listings(self):
        rows = basket()
        rows[0]["reported_weight"] = 0.4
        rows.append(deepcopy(rows[0]))
        self.assertEqual(prepare_holdings(ISIN, rows)[1][0]["weight"], Decimal("80"))

    def test_reject_ambiguous_names(self):
        rows = basket()
        rows[0]["reported_weight"] = 0.4
        rows.append({**rows[0], "isin": "US5949181045"})
        with self.assertRaisesRegex(ValueError, "Different securities"):
            prepare_holdings(ISIN, rows)

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
            instrument_isin="US0378331005", instrument_name="Apple Inc", weight=Decimal("95"))
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


if __name__ == "__main__":
    unittest.main()