"""Offline checks for provider filtering and batch failure isolation."""

from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from import_ishares_holdings_csv import read_ishares, run_batch


class CSVBatchTests(unittest.TestCase):
    def test_filter_normalize_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "etfs.csv"
            path.write_text('isin,provider,asset_class\nIE00B4L5Y983,iShares,Equities\n'
                            'ie00b4l5y983, ISHARES ,Equities\nCH0111762537,UBS,Equities\n', encoding="utf-8-sig")
            self.assertEqual(read_ishares(path), [{"isin": "IE00B4L5Y983", "asset_class": "Equities"}])

    def test_failures_do_not_stop_later_imports(self):
        etfs = [{"isin": isin, "asset_class": asset} for isin, asset in
                [("A", "Equities"), ("B", "Equities"), ("C", "Obligationen"), ("D", "Real Estate")]]
        importer = Mock(side_effect=[ValueError("Invalid provider basket"),
                                    {"isin": "B", "as_of": "2026-09-08", "imported": 10, "replaced": 5}])
        report = StringIO()
        totals = run_batch(etfs, {"A", "B", "C"}, report, importer)
        self.assertEqual(totals, {"imported": 1, "failed": 1, "skipped": 2, "holdings": 10})
        self.assertEqual(importer.call_count, 2)
        self.assertEqual([json.loads(line)["status"] for line in report.getvalue().splitlines()],
                         ["failed", "imported", "skipped", "skipped"])


if __name__ == "__main__":
    unittest.main()