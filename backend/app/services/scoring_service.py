"""
GoETF Scoring Service
Computes individual ETF GoETF Scores (1–10) and Portfolio GoETF Scores.

Individual score = equally weighted absolute quality score across 6 structural
metrics: Holdings HHI, Country Diversity, Sector Diversity, Currency Diversity,
Fund Size, and Number of Holdings. Price-history based metrics are intentionally
excluded for now.

Portfolio score = weighted avg base − overlap penalty + allocation bonus
"""
import math
from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from app.schemas import ETF
from app.services.asset_classes import equity_analytics_supported, normalize_asset_class
from app.services.analytics_service import _holdings_snapshot, _allocation_snapshot, allocation_diversity
from app.services.fx_service import get_latest_rate

# ---------------------------------------------------------------------------
# Scoring configuration
# ---------------------------------------------------------------------------
SCORE_COMPONENTS = (
    "hhi",
    "geo_div",
    "sector_div",
    "currency_div",
    "fund_size_log10",
    "num_holdings",
)

# Absolute reference ranges (worst, best) for each metric.
# Score = clamp((value − worst) / (best − worst), 0, 1)
# For "lower is better" metrics worst > best, so the formula naturally inverts.
SCORE_RANGES = {
    "hhi":              (5000,   50),   # lower is better; worst = 5000, best = 50
    "geo_div":          ( 0.0, 0.80),   # fraction; worst = 0, best = 0.80
    "sector_div":       ( 0.0, 0.80),   # fraction; worst = 0, best = 0.80
    "currency_div":     ( 0.0, 0.80),   # fraction; worst = 0, best = 0.80
    "fund_size_log10":  ( 7.0, 10.0),   # log10(USD); worst = $10M, best = $10B
    "num_holdings":     (   5,  300),   # count; worst = 5 holdings, best = 300
}


# ---------------------------------------------------------------------------
# Raw metric computation for a single ETF
# ---------------------------------------------------------------------------
def _compute_raw_metrics(db: Session, etf: ETF) -> Optional[Dict]:
    """
    Compute the 6 GoETF Quality Score metrics from existing DB tables.
    Returns None if the asset class doesn't support equity-style holdings analytics.
    """
    if not equity_analytics_supported(etf.asset_class):
        return None

    # ── Holdings: HHI ────────────────────────────────────────────────────────
    snapshot = _holdings_snapshot(db, etf.id)
    hhi = None
    num_holdings = None
    if snapshot["status"] == "available":
        num_holdings = len(snapshot["weights"])
        hhi = sum(w * w for w in snapshot["weights"].values())

    # ── Allocations: country, sector, and currency diversification ─────────
    country = _allocation_snapshot(db, etf.id, "country")
    sector = _allocation_snapshot(db, etf.id, "sector")
    currency = _allocation_snapshot(db, etf.id, "currency")
    geo_div, sector_div, currency_div = (
        allocation_diversity(country), allocation_diversity(sector), allocation_diversity(currency),
    )

    # ── Fund size: convert to USD for a currency-neutral comparison ────────
    fund_size_usd = None
    fund_size_log10 = None
    if etf.fund_size and etf.currency:
        rate = get_latest_rate(db, etf.currency)
        if rate:
            fund_size_usd = etf.fund_size * rate
            if fund_size_usd > 0:
                fund_size_log10 = math.log10(fund_size_usd)

    return {
        "hhi": round(hhi, 1) if hhi is not None else None,
        "geo_div": round(geo_div, 4) if geo_div is not None else None,
        "sector_div": round(sector_div, 4) if sector_div is not None else None,
        "currency_div": round(currency_div, 4) if currency_div is not None else None,
        "fund_size_log10": round(fund_size_log10, 4) if fund_size_log10 is not None else None,
        "num_holdings": num_holdings,
        # Extra display fields
        "fund_size_usd": round(fund_size_usd) if fund_size_usd is not None else None,
        "country_coverage": country["coverage"],
        "sector_coverage": sector["coverage"],
        "currency_coverage": currency["coverage"],
    }


# ---------------------------------------------------------------------------
# Absolute metric scorer
# ---------------------------------------------------------------------------
def _absolute_score(metric: str, value: float) -> float:
    """
    Map a raw metric value to a 0–1 quality score using fixed reference ranges.
    0 = worst realistic value, 1 = best realistic value.
    Works for both higher-is-better and lower-is-better metrics because
    SCORE_RANGES encodes direction via (worst, best) ordering.
    """
    worst, best = SCORE_RANGES[metric]
    if best == worst:
        return 0.5
    return max(0.0, min(1.0, (value - worst) / (best - worst)))


# ---------------------------------------------------------------------------
# Public API: compute_goetf_scores
# ---------------------------------------------------------------------------
def compute_goetf_scores(
    db: Session,
    etf_ids: Optional[List[UUID]] = None,
) -> List[Dict]:
    """
    Compute GoETF Score for all ETFs (or a UUID-filtered subset).
    Returns list sorted by score descending (None scores last).
    """
    query = db.query(ETF)
    if etf_ids is not None:
        query = query.filter(ETF.id.in_(etf_ids))
    etfs = query.order_by(ETF.isin).all()

    # Step 1: raw metrics per ETF
    rows = []
    for etf in etfs:
        raw = _compute_raw_metrics(db, etf)
        rows.append({"etf_id": str(etf.id), "isin": etf.isin, "name": etf.name, "metrics": raw,
                     "asset_class": normalize_asset_class(etf.asset_class),
                     "equity_analytics_supported": equity_analytics_supported(etf.asset_class)})

    # Step 2: score each ETF against fixed absolute reference ranges
    results = []
    for row in rows:
        if row["metrics"] is None:
            results.append(
                {
                    "etf_id": row["etf_id"],
                    "isin": row["isin"],
                    "name": row["name"],
                    "goetf_score": None,
                    "insufficient_data": True,
                    "status": "unavailable",
                    "reason": "Unsupported asset class for equity scoring",
                    "asset_class": row["asset_class"],
                    "equity_analytics_supported": row["equity_analytics_supported"],
                }
            )
            continue

        available_components = [
            component for component in SCORE_COMPONENTS
            if row["metrics"].get(component) is not None
        ]
        metric_scores = {
            component: _absolute_score(component, row["metrics"][component])
            for component in available_components
        }
        raw_score = sum(metric_scores.values()) / len(SCORE_COMPONENTS) if len(metric_scores) == len(SCORE_COMPONENTS) else None
        if raw_score is None:
            results.append(
                {
                    "etf_id": row["etf_id"],
                    "isin": row["isin"],
                    "name": row["name"],
                    "goetf_score": None,
                    "insufficient_data": True,
                    "status": "unavailable",
                    "reason": "Missing or unreliable score components: " + ", ".join(c for c in SCORE_COMPONENTS if c not in available_components),
                    "asset_class": row["asset_class"],
                    "equity_analytics_supported": row["equity_analytics_supported"],
                    **row["metrics"],
                    "available_components": available_components,
                    "missing_components": [c for c in SCORE_COMPONENTS if c not in available_components],
                }
            )
            continue
        goetf_score = round(1.0 + raw_score * 9.0, 1)

        results.append(
            {
                "etf_id": row["etf_id"],
                "isin": row["isin"],
                "name": row["name"],
                "goetf_score": goetf_score,
                "status": "available", "reason": None, "insufficient_data": False,
                "asset_class": row["asset_class"],
                "equity_analytics_supported": row["equity_analytics_supported"],
                **row["metrics"],
                "metric_scores": {m: round(metric_scores[m], 3) for m in metric_scores},
                "available_components": available_components,
                "missing_components": [
                    component for component in SCORE_COMPONENTS
                    if component not in available_components
                ],
            }
        )

    results.sort(key=lambda x: x.get("goetf_score") or 0, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Public API: compute_portfolio_score
# ---------------------------------------------------------------------------
def compute_portfolio_score(
    db: Session,
    portfolio: List[Dict],   # [{"etf_id": str(UUID), "weight": float}, ...]
) -> Dict:
    """
    GoETF Portfolio Score.
      base          = Σ w_i * goetf_score_i
      overlap_penalty = weighted avg pairwise weight_overlap * 2  (max 2 pts)
      allocation_bonus= max(0, portfolio_geo_div − avg_individual_geo_div)  (0–1 pt)
      final         = clamp(base − penalty + bonus, 1, 10)
    """
    from app.services.analytics_service import AnalyticsService

    active = [{**p, "etf_id": str(p["etf_id"])} for p in portfolio if p.get("weight", 0) > 0 and p.get("etf_id")]
    if not active:
        return {"error": "No valid ETFs in portfolio"}

    total_w = sum(p["weight"] for p in active)

    # Individual ETF scores used to calculate the portfolio base score.
    all_scores = compute_goetf_scores(db)
    score_map = {s["etf_id"]: s.get("goetf_score") for s in all_scores}
    geo_map = {s["etf_id"]: s.get("geo_div") for s in all_scores}
    isin_map = {s["etf_id"]: s["isin"] for s in all_scores}


    # 1. Base score
    missing_scores = any(score_map.get(p["etf_id"]) is None for p in active)
    base = None if missing_scores else sum((p["weight"] / total_w) * score_map[p["etf_id"]] for p in active)

    # 2. Pairwise weight overlaps
    etf_uuids = [UUID(str(p["etf_id"])) for p in active]
    weights_norm = [p["weight"] / total_w for p in active]
    pairwise_overlaps = []

    for i in range(len(etf_uuids)):
        for j in range(i + 1, len(etf_uuids)):
            ov_result = AnalyticsService.calculate_overlap(db, [etf_uuids[i], etf_uuids[j]])
            pair = next(iter(ov_result.get("matrix", {}).values()), {})
            weight_ov = pair.get("weight_overlap") if pair.get("status") == "available" else None
            combined_w = (weights_norm[i] + weights_norm[j]) / 2
            pairwise_overlaps.append(
                {
                    "etf_a_id": str(etf_uuids[i]),
                    "etf_b_id": str(etf_uuids[j]),
                    "etf_a_isin": isin_map.get(str(etf_uuids[i]), active[i]["etf_id"]),
                    "etf_b_isin": isin_map.get(str(etf_uuids[j]), active[j]["etf_id"]),
                    "weight_overlap_pct": round(float(weight_ov), 1) if weight_ov is not None else None,
                    "status": pair.get("status", "unavailable"), "reason": pair.get("reason"),
                    "as_of_a": pair.get("as_of_a"), "as_of_b": pair.get("as_of_b"),
                    "combined_weight_pct": round(combined_w * 100, 1),
                }
            )

    active_ids = {p["etf_id"] for p in active}
    individual_scores = [
        {**s, "ticker": s["isin"], "weight_pct": round(sum(p["weight"] for p in active if p["etf_id"] == s["etf_id"]) / total_w * 100, 1)}
        for s in all_scores if s["etf_id"] in active_ids
    ]
    if missing_scores or any(p["weight_overlap_pct"] is None for p in pairwise_overlaps):
        return {"portfolio_score": None, "base_score": base, "overlap_penalty": None,
                "allocation_bonus": None, "avg_overlap_pct": None, "portfolio_geo_div": None,
                "status": "unavailable", "reason": "One or more ETF scores or pairwise overlaps are unavailable",
                "pairwise_overlaps": pairwise_overlaps, "individual_scores": individual_scores}

    if pairwise_overlaps:
        total_cw = sum(ov["combined_weight_pct"] for ov in pairwise_overlaps)
        avg_overlap_pct = (
            sum(ov["weight_overlap_pct"] * ov["combined_weight_pct"] for ov in pairwise_overlaps) / total_cw
            if total_cw > 0
            else 0.0
        )
    else:
        avg_overlap_pct = 0.0

    overlap_penalty = (avg_overlap_pct / 100) * 2.0  # max 2 points

    # 3. Allocation spread bonus (portfolio country geo-div vs individual avg)
    norm_portfolio = [
        {"etf_id": UUID(p["etf_id"]), "weight": p["weight"] / total_w * 100}
        for p in active
    ]
    # calculate_portfolio_exposure expects etf_id as UUID in item dict
    exposure = AnalyticsService.calculate_portfolio_exposure(db, norm_portfolio)
    country_vals = list(exposure.get("countries", {}).values())
    allocation_bonus = 0.0
    portfolio_geo_div = None

    if country_vals:
        total_c = sum(country_vals)
        if total_c > 0:
            # Same conservative treatment of unresolved classification as individual scores.
            country_vals[country_vals.index(max(country_vals))] += max(0, 100 - total_c)
            norm_c = [v / max(100, total_c) for v in country_vals]
            port_country_hhi = sum(x * x for x in norm_c) * 10_000
            portfolio_geo_div = round(1.0 - port_country_hhi / 10_000, 3)
            avg_ind_geo = sum(
                (p["weight"] / total_w) * geo_map[p["etf_id"]] for p in active
            )
            allocation_bonus = max(0.0, portfolio_geo_div - avg_ind_geo)

    final_score = max(1.0, min(10.0, base - overlap_penalty + allocation_bonus))

    return {
        "status": "available", "reason": None,
        "portfolio_score": round(final_score, 1),
        "base_score": round(base, 1),
        "overlap_penalty": round(overlap_penalty, 2),
        "allocation_bonus": round(allocation_bonus, 2),
        "avg_overlap_pct": round(avg_overlap_pct, 1),
        "portfolio_geo_div": portfolio_geo_div,
        "pairwise_overlaps": pairwise_overlaps,
        "individual_scores": individual_scores,
    }
