"""Real services and SQL queries against isolated in-memory SQLite, never the live DB."""
import asyncio
from datetime import date, datetime, timedelta
import importlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.schemas import ETF, Holding, Allocation, Performance
from app.models import ETFResponse, ExposureRequest
from app.services.asset_classes import normalize_asset_class, normalize_isin, normalize_bucket
from app.services.analytics_service import AnalyticsService, _allocation_snapshot, _holdings_snapshot
from app.services.scoring_service import compute_goetf_scores, compute_portfolio_score

DAY = date(2026, 9, 8)
APPLE, MICROSOFT, NVIDIA = "US0378331005", "US5949181045", "US67066G1040"


class AssetResponseTests(unittest.TestCase):
    def test_aliases_and_computed_response_from_orm(self):
        cases = [(None, "Unknown", False), ("mystery", "Unknown", False),
                 (" Aktien ", "Equities", True), ("Fixed Income", "Bonds", False),
                 ("Obligationen", "Bonds", False), ("Listed Real Estate", "Real Estate", True),
                 ("Precious Metals", "Commodities", False), ("Geldmarkt", "Money Market", False),
                 ("multi asset", "Multi-Asset", False), ("Crypto", "Digital Assets", False)]
        for raw, category, supported in cases:
            with self.subTest(raw=raw):
                etf = ETF(id=uuid4(), isin="IE00B4L5Y983", name="Test", asset_class=raw,
                          created_at=datetime.now(), updated_at=datetime.now())
                result = ETFResponse.model_validate(etf).model_dump(mode="json")
                self.assertEqual(result["asset_class"], category)
                self.assertEqual(result["equity_analytics_supported"], supported)
                self.assertEqual(etf.asset_class, raw)  # No ORM mutation / DB write.
        self.assertEqual(normalize_asset_class("private property"), "Unknown")

    def test_missing_asset_class_and_forged_flag(self):
        response = ETFResponse(id=uuid4(), isin="IE00B4L5Y983", name="Test",
                               created_at=datetime.now(), updated_at=datetime.now(),
                               equity_analytics_supported=True)
        self.assertFalse(response.model_dump()["equity_analytics_supported"])

    def test_identifiers_and_classifications_are_conservative(self):
        self.assertEqual(normalize_isin(" us0378331005 "), APPLE)
        for bad in (None, "", "US0378331004", "APPLE", "US000000000X"):
            self.assertIsNone(normalize_isin(bad))
        for label in (None, "Unknown", "Other", "unclassified", "ZZ"):
            self.assertIsNone(normalize_bucket(label, "country"))
            self.assertIsNone(normalize_bucket(label, "sector"))
        self.assertEqual(normalize_bucket("UK", "country"), "GB")
        self.assertEqual(normalize_bucket("Switzerland", "country"), "CH")
        self.assertEqual(normalize_bucket("healthcare", "sector"), "Health Care")


class AnalyticsDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (ETF, Holding, Allocation, Performance):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def fund(self, asset="Equities"):
        fund = ETF(id=uuid4(), isin=str(uuid4())[:12], name="Fund", provider="Test",
                   asset_class=asset, ter=0.1)
        self.db.add(fund)
        self.db.flush()
        return fund

    def holding(self, fund, isin=APPLE, weight=100, name="Apple", day=DAY, country="US", sector="Technology"):
        self.db.add(Holding(id=uuid4(), etf_id=fund.id, date=day, instrument_isin=isin,
                            instrument_name=name, weight=weight, country=country, sector=sector))
        self.db.flush()

    def allocation(self, fund, kind, bucket, weight=100, day=DAY):
        self.db.add(Allocation(id=uuid4(), etf_id=fund.id, date=day, type=kind, bucket=bucket, weight=weight))
        self.db.flush()

    def prices(self, fund):
        for i in range(260):
            self.db.add(Performance(id=uuid4(), etf_id=fund.id, date=DAY - timedelta(days=260-i),
                                    close_price=100 * math.exp(i * .001 + .01 * math.sin(i))))
        self.db.flush()

    def pair(self, a, b, day=None):
        result = AnalyticsService.calculate_overlap(self.db, [a.id, b.id], day)
        return next(iter(result["matrix"].values())), result["common_holdings"]

    def portfolio(self, *funds):
        return [{"etf_id": str(f.id), "weight": 100 / len(funds)} for f in funds]

    def test_partial_exposure_retained_for_charts_not_overlap(self):
        a, b = self.fund(), self.fund()
        self.allocation(a, "country", "US", 60)
        self.allocation(a, "country", "Unknown", 40)
        self.allocation(b, "country", "US", 100)
        exposure = AnalyticsService.calculate_portfolio_exposure(self.db, self.portfolio(a))
        self.assertEqual(exposure["countries"], {"US": 60.0})
        self.assertEqual(exposure["exposure_coverage"]["country"]["status"], "partial")
        self.assertEqual(exposure["exposure_coverage"]["country"]["coverage"], 60.0)
        pair = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country")[0]
        self.assertIsNone(pair["weight_overlap"])
        self.assertEqual(pair["status"], "unavailable")

    def test_currency_fallback_uses_holding_currency_not_fund_currency(self):
        fund = self.fund()
        fund.currency = "CHF"
        self.holding(fund)
        exposure = AnalyticsService.calculate_portfolio_exposure(self.db, self.portfolio(fund))
        self.assertEqual(exposure["currencies"], {})
        holding = self.db.query(Holding).filter_by(etf_id=fund.id).one()
        holding.currency = "USD"
        self.db.flush()
        exposure = AnalyticsService.calculate_portfolio_exposure(self.db, self.portfolio(fund))
        self.assertEqual(exposure["currencies"], {"USD": 100.0})
        self.assertEqual(exposure["exposure_coverage"]["currency"]["funds"][0]["source"], "holdings")

    def test_isin_aggregation_not_names(self):
        a, b = self.fund(), self.fund()
        self.holding(a, weight=30)
        self.holding(a, " us0378331005 ", 20, "Apple alternate listing")
        self.holding(a, MICROSOFT, 50, "Same name")
        self.holding(b, APPLE, 40, "Different label")
        self.holding(b, NVIDIA, 60, "Same name")
        row, holdings = self.pair(a, b)
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["weight_overlap"], 40)
        self.assertEqual(row["common_count"], 1)
        self.assertEqual(holdings[0]["isin"], APPLE)
        self.assertEqual(holdings[0]["etf_a_weight"], 50)

    def test_unavailable_is_not_zero(self):
        good = self.fund()
        self.holding(good)
        for asset, isin, weight in [("Bonds", APPLE, 100), (None, APPLE, 100),
                                    ("Equities", None, 100), ("Equities", "US0378331004", 100),
                                    ("Equities", APPLE, 0), ("Equities", APPLE, -5)]:
            with self.subTest(asset=asset, isin=isin, weight=weight):
                bad = self.fund(asset)
                self.holding(bad, isin, weight)
                row, holdings = self.pair(good, bad)
                self.assertEqual(row["status"], "unavailable")
                self.assertIsNone(row["weight_overlap"])
                self.assertTrue(row["reason"])
                self.assertEqual(holdings, [])
        row, _ = self.pair(good, self.fund())
        self.assertIsNone(row["weight_overlap"])

    def test_nonfinite_holdings_are_unavailable(self):
        for weight in (float("nan"), float("inf"), None):
            with self.subTest(weight=weight):
                db = MagicMock()
                query = db.query.return_value
                query.filter.return_value = query
                query.first.return_value = SimpleNamespace(asset_class="Equities")
                query.all.return_value = [SimpleNamespace(weight=weight, instrument_isin=APPLE)]
                snapshot = _holdings_snapshot(db, uuid4(), DAY)
                self.assertEqual(snapshot["status"], "unavailable")
                self.assertEqual(snapshot["reason"], "Invalid holdings weights")

    def test_null_identifiers_never_match_and_zero_weight_ignored(self):
        a, b = self.fund(), self.fund()
        self.holding(a, None, 100, "Same name")
        self.holding(b, None, 100, "Same name")
        row, common = self.pair(a, b)
        self.assertIsNone(row["weight_overlap"])
        self.assertEqual(common, [])
        c, d = self.fund(), self.fund()
        for f in (c, d):
            self.holding(f)
            self.holding(f, None, 0)
        self.assertEqual(self.pair(c, d)[0]["weight_overlap"], 100)

    def test_holdings_dates_and_real_zero(self):
        a, b = self.fund(), self.fund("Real Estate")
        self.holding(a, APPLE, day=DAY-timedelta(days=2))
        self.holding(a, NVIDIA, day=DAY)
        self.holding(b, MICROSOFT, day=DAY-timedelta(days=1))
        row, _ = self.pair(a, b)
        self.assertEqual(row["weight_overlap"], 0)
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["as_of_a"], DAY.isoformat())
        self.assertEqual(row["as_of_b"], (DAY-timedelta(days=1)).isoformat())
        self.assertIsNone(self.pair(a, b, DAY)[0]["weight_overlap"])

    def test_allocations_latest_per_type_aliases_and_dates(self):
        a, b = self.fund(), self.fund()
        for fund in (a, b):
            self.allocation(fund, "sector", "Technology", day=DAY+timedelta(days=1))
        self.allocation(a, "country", "United States", 60)
        self.allocation(a, "country", "US", 40)
        self.allocation(b, "country", "USA", 75, DAY-timedelta(days=1))
        self.allocation(b, "country", "Switzerland", 25, DAY-timedelta(days=1))
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country")[0]
        self.assertEqual(row["weight_overlap"], 75)
        self.assertEqual(row["coverage_a"], 100)
        self.assertEqual(row["source_b"], "allocations")
        self.assertEqual(row["as_of_a"], DAY.isoformat())
        self.assertEqual(row["buckets"][0]["bucket"], "US")
        self.assertEqual(row["buckets"][1]["overlap"], 0)
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country", DAY)[0]
        self.assertIsNone(row["weight_overlap"])

    def test_allocation_full_bucket_list_sorted_by_minimum(self):
        a, b = self.fund(), self.fund()
        sectors = ["Technology", "Healthcare", "Financials", "Consumer Discretionary", "Consumer Staples",
                   "Communication Services", "Industrials", "Materials", "Energy", "Utilities", "Real Estate"]
        for i, sector in enumerate(sectors):
            self.allocation(a, "sector", sector, (i+1) / 66 * 100)
            self.allocation(b, "sector", sector, (11-i) / 66 * 100)
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id])[0]
        self.assertEqual(row["status"], "available")
        self.assertEqual(len(row["buckets"]), 11)
        self.assertEqual(row["buckets"][0]["bucket"], "Communication Services")
        self.assertEqual([r["overlap"] for r in row["buckets"]], sorted((r["overlap"] for r in row["buckets"]), reverse=True))

    def test_unknowns_not_matched_and_no_rescaling(self):
        a, b = self.fund(), self.fund()
        for fund in (a, b):
            self.allocation(fund, "country", "US", 96)
            self.allocation(fund, "country", "Other", 4)
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country")[0]
        self.assertEqual(row["weight_overlap"], 96)
        self.assertEqual(row["coverage_a"], 96)
        self.assertEqual(len(row["buckets"]), 1)
        low = self.fund()
        self.allocation(low, "country", "US", 20)
        self.holding(low, country="US")  # Existing incomplete allocations must not fall back.
        result = _allocation_snapshot(self.db, low.id, "country")
        self.assertEqual(result["source"], "allocations")
        self.assertEqual(result["coverage"], 20)
        self.assertEqual(result["status"], "unavailable")

    def test_holdings_fallback_requires_explicit_reliable_metadata(self):
        a, b, c = self.fund(), self.fund(), self.fund()
        self.holding(a, country="US", sector="Technology")
        self.holding(b, country="US", sector="Information Technology")
        self.holding(c, name="US Technology Company", country=None, sector=None)
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "sector")[0]
        self.assertEqual(row["source_a"], "holdings")
        self.assertEqual(row["weight_overlap"], 100)
        row = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, c.id], "sector")[0]
        self.assertEqual(row["coverage_b"], 0)
        self.assertIsNone(row["weight_overlap"])

    def test_coverage_threshold_and_zero_allocations_do_not_fallback(self):
        for weight, expected in ((95, "available"), (94.99, "unavailable"), (0, "unavailable")):
            with self.subTest(weight=weight):
                fund = self.fund()
                self.allocation(fund, "sector", "Technology", weight)
                self.holding(fund)
                result = _allocation_snapshot(self.db, fund.id, "sector")
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["source"], "allocations")
                self.assertEqual(result["coverage"], weight)

    def test_pinned_allocation_date_selects_history_not_latest(self):
        a, b = self.fund(), self.fund()
        for fund in (a, b):
            self.allocation(fund, "country", "US", day=DAY)
        self.allocation(a, "country", "CH", day=DAY+timedelta(days=1))
        self.assertEqual(AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country")[0]["weight_overlap"], 0)
        result = AnalyticsService.calculate_allocation_overlap(self.db, [a.id, b.id], "country", DAY)[0]
        self.assertEqual(result["weight_overlap"], 100)
        self.assertEqual(result["as_of_a"], DAY.isoformat())

    def test_exposure_and_top_holdings_are_partial_for_mixed_assets(self):
        equity, bond = self.fund(), self.fund("Bonds")
        self.holding(equity)
        self.holding(bond, MICROSOFT)
        for fund in (equity, bond):
            self.allocation(fund, "country", "US")
            self.allocation(fund, "sector", "Technology")
        portfolio = self.portfolio(equity, bond)
        result = AnalyticsService.calculate_portfolio_exposure(self.db, portfolio)
        self.assertEqual(result["countries"], {"US": 50})
        self.assertEqual(result["exposure_coverage"]["country"]["status"], "partial")
        self.assertEqual(result["exposure_coverage"]["country"]["coverage"], 50)
        self.assertTrue(all(isinstance(w, str) for w in result["analysis_warnings"]))
        result = AnalyticsService.calculate_portfolio_top_holdings(self.db, portfolio)
        self.assertEqual(result["top_holdings_status"], "partial")
        self.assertEqual(result["top_holdings_coverage"], 50)
        self.assertEqual(len(result["top_holdings"]), 1)
        self.assertEqual(result["top_holdings"][0]["weight"], 50)

    def test_top_holdings_aggregate_by_isin_and_keep_reported_weights(self):
        a, b = self.fund(), self.fund()
        self.holding(a, APPLE, 40, "Apple")
        self.holding(a, " us0378331005 ", 20, "Apple other listing")
        self.holding(b, APPLE, 80, "APPLE INC")
        result = AnalyticsService.calculate_portfolio_top_holdings(self.db, self.portfolio(a, b))
        self.assertEqual(len(result["top_holdings"]), 1)
        self.assertEqual(result["top_holdings"][0]["weight"], 70)
        self.assertEqual(result["top_holdings_coverage"], 70)

    def test_similar_excludes_unsupported_and_missing_baskets(self):
        a, good, missing, bond = self.fund(), self.fund(), self.fund(), self.fund("Bonds")
        for fund in (a, good, bond):
            self.holding(fund)
        result = AnalyticsService.find_similar_etfs(self.db, a.id)
        self.assertEqual([r["etf_id"] for r in result["similar_etfs"]], [str(good.id)])

    def test_replacements_same_class_and_missing_candidates_excluded(self):
        a, b, c, missing = self.fund(), self.fund(), self.fund("Aktien"), self.fund()
        real_estate, bond = self.fund("Real Estate"), self.fund("Bonds")
        for fund in (a, b):
            self.holding(fund)
        for fund in (c, real_estate, bond):
            self.holding(fund, MICROSOFT)
        portfolio = self.portfolio(a, b)
        result = AnalyticsService.suggest_lower_overlap_alternatives(self.db, portfolio, str(a.id))
        self.assertEqual([r["etf_id"] for r in result["alternatives"]], [str(c.id)])
        pair = AnalyticsService.suggest_pair_replacements(self.db, portfolio, include_replacements=True)[0]
        self.assertEqual(pair["current_overlap"], 100)
        self.assertEqual(pair["best_replacement"]["candidate_etf_id"], str(c.id))
        self.assertEqual(pair["common_holdings"][0]["isin"], APPLE)
        # Default omits the replacement search entirely (used for automatic re-analysis).
        default_pair = AnalyticsService.suggest_pair_replacements(self.db, portfolio)[0]
        self.assertIsNone(default_pair["best_replacement"])
        self.assertEqual(default_pair["current_overlap"], 100)

    def test_pair_suggestions_include_zero_and_unavailable(self):
        a, b, bond = self.fund(), self.fund(), self.fund("Bonds")
        self.holding(a)
        self.holding(b, MICROSOFT)
        pairs = AnalyticsService.suggest_pair_replacements(self.db, self.portfolio(a, b, bond))
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[0]["current_overlap"], 0)
        self.assertEqual(pairs[0]["status"], "available")
        self.assertTrue(all(p["current_overlap"] is None for p in pairs[1:]))
        self.assertTrue(all(p["best_replacement"] is None for p in pairs))
        for pair in pairs:
            self.assertIn("etf_a_isin", pair)
            self.assertIn("etf_b_isin", pair)
            self.assertIn("reason", pair)

    def test_price_risk_remains_available_but_equity_scores_do_not(self):
        bond = self.fund("Fixed Income")
        self.holding(bond)
        self.prices(bond)
        risk = AnalyticsService.calculate_risk_metrics(self.db, etf_id=bond.id)[0]
        self.assertIsNotNone(risk["volatility"])
        self.assertIsNone(risk["hhi"])
        self.assertEqual(risk["hhi_status"], "unavailable")
        score = compute_goetf_scores(self.db)[0]
        self.assertIsNone(score["goetf_score"])
        self.assertEqual(score["status"], "unavailable")
        portfolio = compute_portfolio_score(self.db, self.portfolio(bond))
        self.assertIsNone(portfolio["portfolio_score"])
        self.assertIsNone(portfolio["base_score"])

    def test_diversity_available_without_price_history(self):
        # Country/sector diversity must not be gated behind the price-history
        # requirement used for the composite quality score.
        fund = self.fund()
        self.holding(fund)
        self.allocation(fund, "country", "US", 60)
        self.allocation(fund, "country", "DE", 40)
        self.allocation(fund, "sector", "Information Technology", 100)
        risk = AnalyticsService.calculate_risk_metrics(self.db, etf_id=fund.id)[0]
        self.assertIsNone(risk["volatility"])  # no price rows added
        self.assertAlmostEqual(risk["geo_div"], 1 - (0.6 ** 2 + 0.4 ** 2))
        self.assertEqual(risk["geo_div_status"], "available")
        self.assertEqual(risk["sector_div"], 0.0)
        score = compute_goetf_scores(self.db, etf_ids=[fund.id])[0]
        self.assertIsNone(score["goetf_score"])  # composite score still needs price history

    def test_complete_scores_and_missing_component_not_fallback(self):
        good, bad = self.fund(), self.fund()
        for fund in (good, bad):
            self.prices(fund)
        self.holding(good)
        self.holding(bad, None)
        scores = {r["etf_id"]: r for r in compute_goetf_scores(self.db)}
        self.assertEqual(scores[str(good.id)]["status"], "available")
        self.assertEqual(scores[str(good.id)]["hhi"], 10000)
        self.assertIsNone(scores[str(bad.id)]["goetf_score"])
        self.assertIn("hhi", scores[str(bad.id)]["missing_components"])
        portfolio = compute_portfolio_score(self.db, self.portfolio(good, bad))
        self.assertIsNone(portfolio["portfolio_score"])
        self.assertIsNone(portfolio["pairwise_overlaps"][0]["weight_overlap_pct"])
        self.assertEqual(compute_portfolio_score(self.db, self.portfolio(good))["status"], "available")

    def test_portfolio_rejects_unavailable_overlap_even_with_cached_scores(self):
        a, b = self.fund(), self.fund()
        scores = [{"etf_id": str(f.id), "isin": f.isin, "goetf_score": 8, "geo_div": .5} for f in (a, b)]
        with patch("app.services.scoring_service.compute_goetf_scores", return_value=scores):
            result = compute_portfolio_score(self.db, self.portfolio(a, b))
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["portfolio_score"])
        self.assertIsNone(result["pairwise_overlaps"][0]["weight_overlap_pct"])

    def test_empty_subset_does_not_select_whole_catalog(self):
        self.fund()
        self.assertEqual(AnalyticsService.calculate_risk_metrics(self.db, etf_ids=[]), [])
        self.assertEqual(compute_goetf_scores(self.db, etf_ids=[]), [])

    def test_exposure_route_dates_and_warning_merge_for_single_and_pair(self):
        # Import route without constructing any configured production DB engine.
        with patch.dict(sys.modules, {"app.db.database": SimpleNamespace(get_db=lambda: None)}):
            routes = importlib.import_module("app.api.routes.analytics")
        a, b = self.fund(), self.fund("Bonds")
        self.holding(a)
        for funds in ((a,), (a, b)):
            with patch.object(routes, "resolve_etf", side_effect=lambda db, id_: db.get(ETF, UUID(id_))), \
                 patch.object(AnalyticsService, "calculate_allocation_overlap", wraps=AnalyticsService.calculate_allocation_overlap) as overlap:
                result = asyncio.run(routes.calculate_exposure(ExposureRequest(portfolio=self.portfolio(*funds)),
                                     date=DAY, db=self.db, api_key=None))
                self.assertIsInstance(result, dict)
                self.assertTrue(result["analysis_warnings"])
                if len(funds) == 2:
                    self.assertEqual(overlap.call_count, 2)
                    self.assertTrue(all(call.args[3] == DAY for call in overlap.call_args_list))
                    self.assertTrue(any("holdings" in w for w in result["analysis_warnings"]))


if __name__ == "__main__":
    unittest.main()