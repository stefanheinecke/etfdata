from datetime import date
from typing import List, Dict, Optional
import math
from itertools import combinations
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.schemas import Holding, Allocation, ETF, Performance
from app.services.asset_classes import (
    equity_analytics_supported, normalize_asset_class, normalize_isin, normalize_bucket,
)

MIN_CLASSIFICATION_COVERAGE = 95.0  # Percent of full fund weight, not just known rows.


def _db_id(value):
    return UUID(value) if isinstance(value, str) else value


def _snapshot(db, model, etf_id, requested_date=None, allocation_type=None):
    etf_id = _db_id(etf_id)
    filters = [model.etf_id == etf_id]
    if allocation_type is not None:
        filters.append(model.type == allocation_type)
    as_of = requested_date or db.query(func.max(model.date)).filter(*filters).scalar()
    rows = db.query(model).filter(*filters, model.date == as_of).all() if as_of else []
    return rows, as_of if rows else None


def _iso_date(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _weights(rows):
    try:
        weights = [float(row.weight) for row in rows]
    except (TypeError, ValueError, OverflowError):
        return None
    return weights if all(math.isfinite(w) and w >= 0 for w in weights) else None


def _holdings_snapshot(db, etf_id, requested_date=None):
    etf_id = _db_id(etf_id)
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    rows, as_of = _snapshot(db, Holding, etf_id, requested_date)
    result = {"status": "unavailable", "reason": None, "as_of": _iso_date(as_of),
              "weights": {}, "holdings": {}, "total_weight": 0.0}
    if not etf or not equity_analytics_supported(etf.asset_class):
        result["reason"] = "Unsupported asset class for equity analytics"
        return result
    weights = _weights(rows)
    if not rows or weights == [] or (weights is not None and sum(weights) <= 0):
        result["reason"] = "No positive-weight holdings at requested snapshot"
        return result
    if weights is None:
        result["reason"] = "Invalid holdings weights"
        return result
    total = sum(weights)
    for holding, weight in zip(rows, weights):
        if weight == 0:
            continue
        isin = normalize_isin(holding.instrument_isin)
        if isin is None:
            result["reason"] = "Unresolved or invalid ISIN on positive-weight holdings"
            result["weights"] = {}
            result["holdings"] = {}
            return result
        result["weights"][isin] = result["weights"].get(isin, 0.0) + weight / total * 100
        result["holdings"].setdefault(isin, holding)
    result.update(status="available", total_weight=total)
    return result


def _allocation_snapshot(db, etf_id, allocation_type, requested_date=None):
    etf_id = _db_id(etf_id)
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    rows, as_of = _snapshot(db, Allocation, etf_id, requested_date, allocation_type)
    source = "allocations" if rows else None
    if not rows and allocation_type in {"country", "sector", "currency"}:
        rows, as_of = _snapshot(db, Holding, etf_id, requested_date)
        source = "holdings" if rows else None
    result = {"status": "unavailable", "reason": None, "as_of": _iso_date(as_of),
              "source": source, "coverage": 0.0, "weights": {}}
    if not etf or not equity_analytics_supported(etf.asset_class):
        result["reason"] = "Unsupported asset class for equity analytics"
        return result
    weights = _weights(rows)
    if not rows or weights == [] or (weights is not None and sum(weights) <= 0):
        result["reason"] = f"No positive-weight {allocation_type} data at requested snapshot"
        return result
    if weights is None:
        result["reason"] = f"Invalid {allocation_type} weights"
        return result
    # A tiny classified basket is not 100% coverage. Unknown/Other stays unmatched.
    denominator = max(100.0, sum(weights))
    for row, weight in zip(rows, weights):
        label = row.bucket if source == "allocations" else getattr(row, allocation_type, None)
        bucket = normalize_bucket(label, allocation_type)
        if bucket and weight > 0:
            result["weights"][bucket] = result["weights"].get(bucket, 0.0) + weight / denominator * 100
    coverage = sum(result["weights"].values())
    result["coverage"] = round(coverage, 2)
    if coverage + 1e-9 < MIN_CLASSIFICATION_COVERAGE:
        result["reason"] = f"Insufficient {allocation_type} classification coverage (requires {MIN_CLASSIFICATION_COVERAGE:g}%)"
    else:
        result["status"] = "available"
    return result


def _pair_status(a, b):
    reasons = [f"ETF {label}: {snapshot['reason']}" for label, snapshot in (("A", a), ("B", b))
               if snapshot["status"] != "available"]
    return {"status": "unavailable" if reasons else "available",
            "reason": "; ".join(reasons) or None,
            "as_of_a": a["as_of"], "as_of_b": b["as_of"]}

def allocation_diversity(allocation):
    """1 - HHI-style concentration on classified country/sector weights.
    Conservative: unresolved exposure is folded into the largest known bucket."""
    if allocation["status"] != "available":
        return None
    weights = list(allocation["weights"].values())
    weights[weights.index(max(weights))] += max(0, 100 - sum(weights))
    return 1.0 - sum((w / 100) ** 2 for w in weights)

class AnalyticsService:
    @staticmethod
    def calculate_overlap(db: Session, etf_ids: List[UUID], overlap_date: Optional[date] = None):
        if not etf_ids or len(etf_ids) < 2:
            return {"error": "At least 2 ETFs required"}
        snapshots = {str(id_): _holdings_snapshot(db, id_, overlap_date) for id_ in etf_ids}
        matrix = {}
        common_holdings = []
        for etf_a, etf_b in combinations(etf_ids, 2):
            a_id, b_id = str(etf_a), str(etf_b)
            a, b = snapshots[a_id], snapshots[b_id]
            row = {"etf_a": a_id, "etf_b": b_id, "common_count": None,
                   "overlap_percent": None, "weight_overlap": None, **_pair_status(a, b)}
            key = f"{a_id[:8]}_{b_id[:8]}"
            if key in matrix:  # Preserve legacy keys without losing UUID-prefix collisions.
                key = f"{a_id}_{b_id}"
            matrix[key] = row
            if row["status"] != "available":
                continue
            common = a["weights"].keys() & b["weights"].keys()
            row.update(common_count=len(common),
                       overlap_percent=round(len(common) / max(len(a["weights"]), len(b["weights"])) * 100, 2),
                       weight_overlap=round(sum(min(a["weights"][isin], b["weights"][isin]) for isin in common), 2))
            for isin in common:
                common_holdings.append({"isin": isin, "name": a["holdings"][isin].instrument_name,
                                        "etf_a": a_id, "etf_b": b_id,
                                        "etf_a_weight": round(a["weights"][isin], 4),
                                        "etf_b_weight": round(b["weights"][isin], 4)})
        common_holdings.sort(key=lambda h: (
            -min(h["etf_a_weight"], h["etf_b_weight"]), h["name"], h["isin"]
        ))
        return {"matrix": matrix, "common_holdings": common_holdings[:20]}

    @staticmethod
    def calculate_portfolio_exposure(db: Session, portfolio: List[Dict], exposure_date: Optional[date] = None):
        active = [p for p in portfolio if p.get("weight", 0) > 0]
        total = sum(p["weight"] for p in active)
        output = {"analysis_warnings": [], "exposure_coverage": {}}
        for kind, field in (("sector", "sectors"), ("country", "countries"), ("currency", "currencies")):
            buckets, covered, sources = {}, 0.0, []
            for item in active:
                snapshot = _allocation_snapshot(db, item["etf_id"], kind, exposure_date)
                sources.append({"etf_id": str(item["etf_id"]), **{k: v for k, v in snapshot.items() if k != "weights"}})
                if snapshot["status"] != "available":
                    output["analysis_warnings"].append(f"{item['etf_id']} ({kind}): {snapshot['reason']}")
                    # Charts can display explicitly classified partial exposure.
                    # Pair overlap still requires the stricter coverage threshold.
                covered += item["weight"] * snapshot["coverage"] / 100
                for bucket, weight in snapshot["weights"].items():
                    buckets[bucket] = buckets.get(bucket, 0.0) + weight * item["weight"] / 100
            coverage = covered / total * 100 if total else 0.0
            status = "available" if coverage >= 99.995 else "partial" if covered else "unavailable"
            output[field] = {k: round(v, 2) for k, v in sorted(buckets.items(), key=lambda x: (-x[1], x[0]))}
            output["exposure_coverage"][kind] = {"status": status, "coverage": round(coverage, 2), "funds": sources}
            if status != "available":
                output["analysis_warnings"].append(f"{kind.title()} exposure is {status}; covers {coverage:.2f}% of portfolio weight. Totals are not rescaled.")
        return output

    @staticmethod
    def find_similar_etfs(db: Session, etf_id: UUID, top_n: int = 5):
        target_etf = db.query(ETF).filter(ETF.id == etf_id).first()
        if not target_etf:
            return {"error": "ETF not found"}
        if not equity_analytics_supported(target_etf.asset_class):
            return {"similar_etfs": [], "status": "unavailable", "reason": "Unsupported asset class for equity analytics"}

        all_etfs = db.query(ETF).filter(ETF.id != etf_id).limit(50).all()

        similarities = []

        for other_etf in all_etfs:
            if not equity_analytics_supported(other_etf.asset_class):
                continue
            overlap_result = AnalyticsService.calculate_overlap(
                db, [etf_id, other_etf.id]
            )

            if "matrix" in overlap_result and overlap_result["matrix"]:
                for overlap_data in overlap_result["matrix"].values():
                    if overlap_data.get("status") != "available" or overlap_data.get("weight_overlap") is None:
                        continue
                    score = overlap_data["overlap_percent"]
                    similarities.append({
                        "etf_id": str(other_etf.id),
                        "isin": other_etf.isin,
                        "name": other_etf.name,
                        "provider": other_etf.provider,
                        "similarity_score": round(score, 2)
                    })

        similar_etfs = sorted(similarities, key=lambda x: x["similarity_score"], reverse=True)[:top_n]

        return {"similar_etfs": similar_etfs}

    @staticmethod
    def calculate_risk_metrics(db: Session, rf_annual: float = 0.04, etf_id: Optional[UUID] = None, etf_ids: Optional[List[UUID]] = None) -> list:
        """Compute annualized volatility, Sharpe ratio, max drawdown, and HHI for every ETF.
        Pass etf_id to compute for a single ETF, etf_ids for a specific subset, or neither for all.
        """
        import math

        query = db.query(ETF)
        if etf_ids is not None:
            query = query.filter(ETF.id.in_(etf_ids))
        elif etf_id:
            query = query.filter(ETF.id == etf_id)
        else:
            query = query.order_by(ETF.isin)
        etfs = query.all()
        results = []

        for etf in etfs:
            row: dict = {
                "etf_id":       str(etf.id),
                "isin":         etf.isin,
                "name":         etf.name,
                "volatility":   None,
                "sharpe_ratio": None,
                "max_drawdown": None,
                "ann_return":   None,
                "data_points":  0,
                "hhi":          None,
                "num_holdings": 0,
            }

            # ── Price-based metrics ──────────────────────────────────────────
            perf = (
                db.query(Performance)
                .filter(Performance.etf_id == etf.id)
                .order_by(Performance.date)
                .all()
            )
            prices = [float(p.close_price) for p in perf if p.close_price is not None and p.close_price > 0]
            row["data_points"] = len(prices)

            if len(prices) >= 20:
                log_returns = [
                    math.log(prices[i] / prices[i - 1])
                    for i in range(1, len(prices))
                ]
                n = len(log_returns)
                mean_r   = sum(log_returns) / n
                variance = sum((r - mean_r) ** 2 for r in log_returns) / (n - 1)
                daily_vol = math.sqrt(variance)

                ann_vol    = daily_vol * math.sqrt(252)
                ann_return = mean_r    * 252

                rf_daily = rf_annual / 252
                sharpe   = ((mean_r - rf_daily) / daily_vol * math.sqrt(252)) if daily_vol > 0 else None

                # Max drawdown (peak-to-trough)
                peak   = prices[0]
                max_dd = 0.0
                for p in prices[1:]:
                    if p > peak:
                        peak = p
                    dd = (p - peak) / peak
                    if dd < max_dd:
                        max_dd = dd

                row["volatility"]   = round(ann_vol    * 100, 2)
                row["sharpe_ratio"] = round(sharpe,       3) if sharpe is not None else None
                row["max_drawdown"] = round(max_dd     * 100, 2)   # negative
                row["ann_return"]   = round(ann_return * 100, 2)

            # ── HHI from latest holdings ─────────────────────────────────────
            snapshot = _holdings_snapshot(db, etf.id)
            row.update(asset_class=normalize_asset_class(etf.asset_class),
                       equity_analytics_supported=equity_analytics_supported(etf.asset_class),
                       hhi_status=snapshot["status"], hhi_reason=snapshot["reason"])
            if snapshot["status"] == "available":
                row["num_holdings"] = len(snapshot["weights"])
                row["hhi"] = round(sum(w * w for w in snapshot["weights"].values()), 1)
            # ── Country/sector diversity from allocations, independent of price history ──
            for kind in ("country", "sector"):
                alloc = _allocation_snapshot(db, etf.id, kind)
                key = "geo_div" if kind == "country" else "sector_div"
                value = allocation_diversity(alloc)
                row[key] = round(value, 4) if value is not None else None
                row[f"{key}_status"] = alloc["status"]
                row[f"{key}_reason"] = alloc["reason"]
            results.append(row)

        return results

    @staticmethod
    def calculate_portfolio_top_holdings(db: Session, portfolio: List[Dict], top_n: int = 10, holdings_date: Optional[date] = None):
        """Get the top N weighted holdings across a portfolio from the latest available date."""
        holdings_dict = {}
        active = [p for p in portfolio if p.get("weight", 0) > 0]
        total = sum(p["weight"] for p in active)
        covered, warnings, funds = 0.0, [], []
        for item in active:
            snapshot = _holdings_snapshot(db, item["etf_id"], holdings_date)
            funds.append({"etf_id": str(item["etf_id"]), "status": snapshot["status"],
                          "reason": snapshot["reason"], "as_of": snapshot["as_of"]})
            if snapshot["status"] != "available":
                warnings.append(f"{item['etf_id']} (holdings): {snapshot['reason']}")
                continue
            covered += item["weight"] * min(snapshot["total_weight"], 100) / 100
            for isin, normalized_weight in snapshot["weights"].items():
                holding = snapshot["holdings"][isin]
                # Preserve reported NAV weights, not normalized basket weights.
                weight = normalized_weight * snapshot["total_weight"] / 100 * item["weight"] / 100
                if isin not in holdings_dict:
                    holdings_dict[isin] = {"name": holding.instrument_name, "isin": isin,
                                           "sector": normalize_bucket(holding.sector, "sector"),
                                           "country": normalize_bucket(holding.country, "country"),
                                           "currency": normalize_bucket(holding.currency, "currency"), "weight": 0.0}
                elif holdings_dict[isin]["currency"] != normalize_bucket(holding.currency, "currency"):
                    holdings_dict[isin]["currency"] = None
                holdings_dict[isin]["weight"] += weight
        sorted_holdings = sorted(holdings_dict.values(), key=lambda x: (-x["weight"], x["isin"]))[:top_n]
        for holding in sorted_holdings:
            holding["weight"] = round(holding["weight"], 2)
        coverage = covered / total * 100 if total else 0.0
        status = "available" if coverage >= 99.995 else "partial" if covered else "unavailable"
        if status != "available":
            warnings.append(f"Top holdings are {status}; source baskets cover {coverage:.2f}% of portfolio weight. Totals are not rescaled.")
        return {"top_holdings": sorted_holdings, "top_holdings_status": status,
                "top_holdings_coverage": round(coverage, 2), "top_holdings_funds": funds,
                "analysis_warnings": warnings}

    @staticmethod
    def calculate_allocation_overlap(db: Session, etf_ids: List[UUID], alloc_type: str = "sector", overlap_date: Optional[date] = None):
        """Overlap in sector or country allocations between each pair of ETFs."""
        if alloc_type not in {"sector", "country"}:
            raise ValueError("Allocation overlap type must be sector or country")
        alloc_data = {}
        etf_meta = {}
        for etf_id in etf_ids:
            etf = db.query(ETF).filter(ETF.id == etf_id).first()
            etf_meta[str(etf_id)] = {"isin": etf.isin if etf else str(etf_id)[:8], "name": etf.name if etf else ""}
            alloc_data[str(etf_id)] = _allocation_snapshot(db, etf_id, alloc_type, overlap_date)

        pairs = []
        for i, etf_a in enumerate(etf_ids):
            for etf_b in etf_ids[i + 1:]:
                a_str, b_str = str(etf_a), str(etf_b)
                a, b = alloc_data[a_str], alloc_data[b_str]
                status = _pair_status(a, b)
                data_a, data_b = a["weights"], b["weights"]
                all_buckets = set(data_a) | set(data_b)
                weight_overlap = sum(min(data_a.get(b, 0), data_b.get(b, 0)) for b in all_buckets)
                top_buckets = sorted(
                    [{"bucket": bucket, "etf_a_weight": round(data_a.get(bucket, 0), 4), "etf_b_weight": round(data_b.get(bucket, 0), 4), "overlap": round(min(data_a.get(bucket, 0), data_b.get(bucket, 0)), 4)} for bucket in all_buckets],
                    key=lambda x: (-x["overlap"], x["bucket"])
                )
                pairs.append({
                    "etf_a": a_str, "etf_b": b_str,
                    "etf_a_isin": etf_meta[a_str]["isin"], "etf_b_isin": etf_meta[b_str]["isin"],
                    "type": alloc_type,
                    **status,
                    "coverage_a": a["coverage"], "coverage_b": b["coverage"],
                    "source_a": a["source"], "source_b": b["source"],
                    "weight_overlap": round(weight_overlap, 2) if status["status"] == "available" else None,
                    "buckets": top_buckets if status["status"] == "available" else [],
                })
        pairs.sort(key=lambda p: (p["weight_overlap"] is None, -(p["weight_overlap"] or 0)))
        return pairs

    @staticmethod
    def suggest_lower_overlap_alternatives(db: Session, portfolio: List[Dict], replace_etf_id: str, top_n: int = 5):
        """Find ETFs not in portfolio that would have the least holdings overlap with the rest of portfolio."""
        rest = [p for p in portfolio if str(p["etf_id"]) != str(replace_etf_id) and p.get("weight", 0) > 0]
        replaced = db.query(ETF).filter(ETF.id == _db_id(replace_etf_id)).first()
        if not rest or not replaced or not equity_analytics_supported(replaced.asset_class):
            return {"alternatives": [], "replaced_etf_id": replace_etf_id}
        if _holdings_snapshot(db, replace_etf_id)["status"] != "available":
            return {"alternatives": [], "replaced_etf_id": replace_etf_id}

        portfolio_ids = {UUID(str(p["etf_id"])) for p in portfolio}
        candidates = db.query(ETF).filter(ETF.id.notin_(portfolio_ids)).limit(50).all()
        total_rest_weight = sum(p["weight"] for p in rest) or 1

        results = []
        for candidate in candidates:
            if normalize_asset_class(candidate.asset_class) != normalize_asset_class(replaced.asset_class):
                continue
            weighted_overlap = 0.0
            available = True
            for p in rest:
                ov = AnalyticsService.calculate_overlap(db, [UUID(str(p["etf_id"])), candidate.id])
                row = next(iter(ov.get("matrix", {}).values()), {})
                if row.get("status") != "available" or row.get("weight_overlap") is None:
                    available = False
                    break
                weighted_overlap += row["weight_overlap"] * p["weight"] / total_rest_weight
            if not available:
                continue
            results.append({
                "etf_id": str(candidate.id),
                "isin": candidate.isin,
                "name": candidate.name,
                "provider": candidate.provider,
                "ter": float(candidate.ter) if candidate.ter is not None else None,
                "overlap_with_portfolio": round(weighted_overlap, 1),
            })

        results.sort(key=lambda x: x["overlap_with_portfolio"])
        return {"alternatives": results[:top_n], "replaced_etf_id": replace_etf_id}

    @staticmethod
    def suggest_pair_replacements(db: Session, portfolio: List[Dict], candidate_limit: int = 30,
                                  include_replacements: bool = False):
        """Return every pair, including genuine zero overlap and unavailable comparisons.

        Replacement-candidate search is opt-in: it scores the whole catalog and
        re-runs overlap per candidate, which is too slow for automatic re-analysis.
        """
        if len(portfolio) < 2:
            return []

        score_map = {}
        candidates = []
        if include_replacements:
            from app.services.scoring_service import compute_goetf_scores
            all_scores = compute_goetf_scores(db)
            score_map = {s["etf_id"]: s.get("goetf_score") for s in all_scores}

        etf_ids = list(dict.fromkeys(UUID(str(p["etf_id"])) for p in portfolio))
        if include_replacements:
            candidates = db.query(ETF).filter(ETF.id.notin_(etf_ids)).limit(candidate_limit).all()

        def get_overlap(id_a, id_b):
            result = AnalyticsService.calculate_overlap(db, [id_a, id_b])
            row = next(iter(result.get("matrix", {}).values()), {})
            return row.get("weight_overlap") if row.get("status") == "available" else None

        suggestions = []
        for i, etf_a in enumerate(etf_ids):
            for etf_b in etf_ids[i + 1:]:
                pair_overlap = AnalyticsService.calculate_overlap(db, [etf_a, etf_b])
                pair = next(iter(pair_overlap["matrix"].values()))
                current_overlap = pair["weight_overlap"]

                common_holdings = sorted(
                    (
                        {
                            "isin": h["isin"],
                            "name": h["name"],
                            "etf_a_weight": h["etf_a_weight"],
                            "etf_b_weight": h["etf_b_weight"],
                            "overlap": round(min(h["etf_a_weight"], h["etf_b_weight"]), 4),
                        }
                        for h in pair_overlap.get("common_holdings", [])
                    ),
                    key=lambda h: h["overlap"],
                    reverse=True,
                )

                etf_a_obj = db.query(ETF).filter(ETF.id == etf_a).first()
                etf_b_obj = db.query(ETF).filter(ETF.id == etf_b).first()

                best = None
                best_reduction = 0.0

                for c in candidates:
                    if current_overlap is None or current_overlap <= 0 or not equity_analytics_supported(c.asset_class):
                        continue
                    for replaced, remaining in ((etf_a_obj, etf_b), (etf_b_obj, etf_a)):
                        if not replaced or normalize_asset_class(c.asset_class) != normalize_asset_class(replaced.asset_class):
                            continue
                        new_ov = get_overlap(c.id, remaining)
                        if new_ov is None:
                            continue
                        reduction = current_overlap - new_ov
                        if reduction <= best_reduction:
                            continue
                        best_reduction = reduction
                        best = {"replace_etf_id": str(replaced.id), "replace_isin": replaced.isin,
                                "replace_ter": float(replaced.ter) if replaced.ter is not None else None,
                                "replace_goetf_score": score_map.get(str(replaced.id)),
                                "candidate_etf_id": str(c.id), "candidate_isin": c.isin,
                                "candidate_name": c.name, "candidate_provider": c.provider,
                                "candidate_ter": float(c.ter) if c.ter is not None else None,
                                "candidate_goetf_score": score_map.get(str(c.id)),
                                "new_overlap": round(new_ov, 1), "reduction": round(reduction, 1)}

                suggestions.append({
                    "etf_a_id": str(etf_a), "etf_a_isin": etf_a_obj.isin if etf_a_obj else None,
                    "etf_b_id": str(etf_b), "etf_b_isin": etf_b_obj.isin if etf_b_obj else None,
                    "current_overlap": round(current_overlap, 1) if current_overlap is not None else None,
                    **{key: pair[key] for key in ("status", "reason", "as_of_a", "as_of_b")},
                    "common_holdings": common_holdings,
                    "best_replacement": best,
                })

        suggestions.sort(key=lambda x: (x["current_overlap"] is None, -(x["current_overlap"] or 0)))
        return suggestions
