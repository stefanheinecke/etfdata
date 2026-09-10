"""Offline regression tests for the overlap calculation's top-20 ranking."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[2]


def load_calculate_overlap():
    """Execute the actual method without requiring SQLAlchemy or a database."""
    path = ROOT / "backend/app/services/analytics_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    service = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "AnalyticsService")
    method = next(node for node in service.body if isinstance(node, ast.FunctionDef)
                  and node.name == "calculate_overlap")
    method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])
    namespace = {"Holding": MagicMock(), "func": MagicMock()}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["calculate_overlap"]


class OverlapRankingTests(unittest.TestCase):
    def calculate(self, first, second):
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.all.side_effect = [first, second]
        return load_calculate_overlap()(db, ["ETF-A", "ETF-B"], overlap_date="2026-09-08")

    def test_provider_baskets_rank_nvidia_before_apple(self):
        baskets = []
        for isin in ("IE00B4L5Y983", "IE00B5BMR087"):
            rows = json.loads((ROOT / f"astra/holdings_{isin}.json").read_text(encoding="utf-8"))
            baskets.append([SimpleNamespace(instrument_name=row["name"],
                                            weight=row["reported_weight"] * 100)
                            for row in rows])
        result = self.calculate(*baskets)
        names = [holding["name"] for holding in result["common_holdings"]]
        self.assertEqual(names[:2], ["NVIDIA", "APPLE"])
        self.assertEqual(len(names), 20)
        self.assertGreater(result["matrix"]["ETF-A_ETF-B"]["common_count"], 20)

    def test_rank_by_smaller_weight_not_combined_weight(self):
        names = [f"Holding {i:02}" for i in range(30)]
        first = [SimpleNamespace(instrument_name=name, weight=i + 1)
                 for i, name in enumerate(names)]
        second = [SimpleNamespace(instrument_name=name, weight=30 - i)
                  for i, name in enumerate(names)]
        result = self.calculate(first, second)
        expected = sorted(names, key=lambda name: (
            -min(names.index(name) + 1, 30 - names.index(name)), name))[:20]
        self.assertEqual([h["name"] for h in result["common_holdings"]], expected)
        expected_overlap = sum(min(i + 1, 30 - i) for i in range(30)) / 465 * 100
        self.assertEqual(result["matrix"]["ETF-A_ETF-B"]["weight_overlap"], round(expected_overlap, 2))

    def test_no_common_holdings(self):
        result = self.calculate([SimpleNamespace(instrument_name="A", weight=100)],
                                [SimpleNamespace(instrument_name="B", weight=100)])
        self.assertEqual(result["common_holdings"], [])
        self.assertEqual(result["matrix"]["ETF-A_ETF-B"]["weight_overlap"], 0)


if __name__ == "__main__":
    unittest.main()