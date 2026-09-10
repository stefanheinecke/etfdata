"""Offline regression tests for the overlap calculation's top-20 ranking."""

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import unittest
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
A = UUID("11111111-0000-0000-0000-000000000000")
B = UUID("22222222-0000-0000-0000-000000000000")
PAIR_KEY = "11111111_22222222"


def load_calculate_overlap():
    """Use the real service when installed; AST fallback includes its actual helpers."""
    try:
        import sqlalchemy
    except ModuleNotFoundError:
        pass
    else:
        from app.services.analytics_service import AnalyticsService
        return AnalyticsService.calculate_overlap
    path = ROOT / "backend/app/services/analytics_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    service = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "AnalyticsService")
    method = next(node for node in service.body if isinstance(node, ast.FunctionDef)
                  and node.name == "calculate_overlap")
    method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *[node for node in tree.body if isinstance(node, ast.FunctionDef)],
        method,
    ], type_ignores=[])
    import math
    from itertools import combinations
    from app.services.asset_classes import normalize_isin, equity_analytics_supported
    namespace = {"Holding": MagicMock(), "ETF": MagicMock(), "func": MagicMock(),
                 "math": math, "combinations": combinations, "UUID": UUID,
                 "normalize_isin": normalize_isin, "equity_analytics_supported": equity_analytics_supported}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["calculate_overlap"]


class OverlapRankingTests(unittest.TestCase):
    def calculate(self, first, second):
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.first.return_value = SimpleNamespace(asset_class="Equities")
        query.all.side_effect = [first, second]
        return load_calculate_overlap()(db, [A, B], overlap_date="2026-09-08")

    def test_provider_baskets_rank_nvidia_before_apple(self):
        baskets = []
        for isin in ("IE00B4L5Y983", "IE00B5BMR087"):
            rows = json.loads((ROOT / f"astra/holdings_{isin}.json").read_text(encoding="utf-8"))
            baskets.append([SimpleNamespace(instrument_name=row["name"],
                                            instrument_isin=row["isin"],
                                            weight=row["reported_weight"] * 100)
                            for row in rows])
        result = self.calculate(*baskets)
        names = [holding["name"] for holding in result["common_holdings"]]
        self.assertEqual(names[:2], ["NVIDIA", "APPLE"])
        self.assertEqual(len(names), 20)
        self.assertGreater(result["matrix"][PAIR_KEY]["common_count"], 20)

    def test_rank_by_smaller_weight_not_combined_weight(self):
        names = [f"Holding {i:02}" for i in range(30)]
        rows = json.loads((ROOT / "astra/holdings_IE00B4L5Y983.json").read_text(encoding="utf-8"))
        isins = list(dict.fromkeys(row["isin"] for row in rows))[:30]
        first = [SimpleNamespace(instrument_name=name, instrument_isin=isins[i], weight=i + 1)
                 for i, name in enumerate(names)]
        second = [SimpleNamespace(instrument_name=name, instrument_isin=isins[i], weight=30 - i)
                  for i, name in enumerate(names)]
        result = self.calculate(first, second)
        expected = sorted(names, key=lambda name: (
            -min(names.index(name) + 1, 30 - names.index(name)), name))[:20]
        self.assertEqual([h["name"] for h in result["common_holdings"]], expected)
        expected_overlap = sum(min(i + 1, 30 - i) for i in range(30)) / 465 * 100
        self.assertEqual(result["matrix"][PAIR_KEY]["weight_overlap"], round(expected_overlap, 2))

    def test_no_common_holdings(self):
        result = self.calculate([SimpleNamespace(instrument_name="A", instrument_isin="US0378331005", weight=100)],
                    [SimpleNamespace(instrument_name="B", instrument_isin="US5949181045", weight=100)])
        self.assertEqual(result["common_holdings"], [])
        self.assertEqual(result["matrix"][PAIR_KEY]["weight_overlap"], 0)


if __name__ == "__main__":
    unittest.main()