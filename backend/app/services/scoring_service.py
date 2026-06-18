"""
GoETF Scoring Service
Computes individual ETF GoETF Scores (1–10) and Portfolio GoETF Scores.

Individual score = weighted percentile rank across 8 metrics:
  Sortino (20%), Calmar (15%), CVaR (15%), HHI (10%),
  Effective N (10%), Geo Div (10%), Hit Ratio (10%), Max Underwater (10%)

Portfolio score = weighted avg base − overlap penalty + allocation bonus
"""
import math
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.schemas import ETF, Performance, Holding, Allocation

# ---------------------------------------------------------------------------
# Scoring configuration
# ---------------------------------------------------------------------------
SCORE_WEIGHTS = {
    "sortino": 0.20,
    "calmar": 0.15,
    "cvar": 0.15,
    "hhi": 0.10,
    "effective_n": 0.10,
    "geo_div": 0.10,
    "hit_ratio": 0.10,
    "max_underwater": 0.10,
}

# True = higher value is better; False = lower value is better
HIGHER_IS_BETTER = {
    "sortino": True,
    "calmar": True,
    "cvar": True,       # CVaR expressed as annualised return (negative = loss); less negative = better
    "hhi": False,
    "effective_n": True,
    "geo_div": True,
    "hit_ratio": True,
    "max_underwater": False,
}

# Absolute reference ranges (worst, best) for each metric.
# Score = clamp((value − worst) / (best − worst), 0, 1)
# For "lower is better" metrics worst > best, so the formula naturally inverts.
SCORE_RANGES = {
    # metric: (worst, best) — score = clamp((value − worst) / (best − worst), 0, 1)
    # For "lower is better" metrics worst > best, so the formula naturally inverts.
    # "best" values represent genuinely excellent but achievable equity ETF performance.
    "sortino":        (-0.5,   1.5),   # ratio; worst = −0.5, best = 1.5
    "calmar":         (-0.2,   0.7),   # ratio; worst = −0.2, best = 0.7
    "cvar":           (-80.0, -15.0),  # %; worst = −80%, best = −15%
    "hit_ratio":      ( 0.40,  0.60),  # fraction; worst = 40%, best = 60%
    "hhi":            (5000,   50),    # lower is better; worst = 5000, best = 50
    "effective_n":    (   1,  200),    # higher is better; worst = 1, best = 200
    "geo_div":        ( 0.0,   0.80),  # fraction; worst = 0, best = 0.80
    "max_underwater": (2500,   50),    # days; lower is better; worst = 2500, best = 50
}


# ---------------------------------------------------------------------------
# Raw metric computation for a single ETF
# ---------------------------------------------------------------------------
def _compute_raw_metrics(db: Session, etf: ETF, rf_annual: float) -> Optional[Dict]:
    """
    Compute all 8 raw metrics for a single ETF from existing DB tables.
    Returns None if there is insufficient price history (< 30 data points).
    """
    perf = (
        db.query(Performance)
        .filter(Performance.etf_id == etf.id)
        .order_by(Performance.date)
        .all()
    )
    prices = [float(p.close_price) for p in perf if p.close_price is not None]

    if len(prices) < 30:
        return None

    rf_daily = rf_annual / 252
    daily_returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    n = len(daily_returns)
    mean_r = sum(daily_returns) / n
    variance = sum((r - mean_r) ** 2 for r in daily_returns) / max(n - 1, 1)
    daily_vol = math.sqrt(variance)
    ann_return = mean_r * 252
    ann_vol = daily_vol * math.sqrt(252)

    # 1. Sortino Ratio
    excess = [r - rf_daily for r in daily_returns]
    downside = [e for e in excess if e < 0]
    if len(downside) > 1:
        down_var = sum(d ** 2 for d in downside) / (len(downside) - 1)
    else:
        down_var = variance
    downside_dev_ann = math.sqrt(down_var) * math.sqrt(252)
    sortino = (ann_return - rf_annual) / downside_dev_ann if downside_dev_ann > 0 else 0.0

    # 2. Calmar Ratio (annualised return / |max drawdown|)
    peak = prices[0]
    max_dd = 0.0
    for p in prices[1:]:
        if p > peak:
            peak = p
        dd = (p - peak) / peak
        if dd < max_dd:
            max_dd = dd
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # 3. CVaR 95% — mean of worst 5 % of daily log-returns, annualised via sqrt-of-time rule
    sorted_r = sorted(daily_returns)
    n_tail = max(1, int(n * 0.05))
    cvar_daily = sum(sorted_r[:n_tail]) / n_tail  # average worst-day log-return (e.g. -0.026)
    cvar_ann = cvar_daily * math.sqrt(252)        # scale by √252 (same as volatility)

    # 4. Hit Ratio — fraction of days with positive return
    hit_ratio = sum(1 for r in daily_returns if r > 0) / n

    # 5. Max Time Under Water (trading days)
    max_underwater = 0
    current_uw = 0
    peak_price = prices[0]
    for p in prices[1:]:
        if p >= peak_price:
            peak_price = p
            current_uw = 0
        else:
            current_uw += 1
            if current_uw > max_underwater:
                max_underwater = current_uw

    # ── Holdings: HHI & Effective N ──────────────────────────────────────────
    latest_holding_date = (
        db.query(func.max(Holding.date)).filter(Holding.etf_id == etf.id).scalar()
    )
    hhi = 10000.0
    effective_n = 1.0
    num_holdings = 0
    if latest_holding_date:
        holdings = (
            db.query(Holding)
            .filter(Holding.etf_id == etf.id, Holding.date == latest_holding_date)
            .all()
        )
        w = [float(h.weight) for h in holdings if h.weight is not None]
        total_w = sum(w)
        num_holdings = len(w)
        if total_w > 0 and len(w) > 0:
            norm = [x / total_w for x in w]
            sum_sq = sum(x * x for x in norm)
            hhi = sum_sq * 10_000
            effective_n = 1.0 / sum_sq if sum_sq > 0 else float(len(w))

    # ── Allocations: Geographic Diversification Score ─────────────────────────
    latest_alloc_date = (
        db.query(func.max(Allocation.date))
        .filter(Allocation.etf_id == etf.id, Allocation.type == "country")
        .scalar()
    )
    geo_div = 0.5  # neutral default when no country data
    if latest_alloc_date:
        allocs = (
            db.query(Allocation)
            .filter(
                Allocation.etf_id == etf.id,
                Allocation.type == "country",
                Allocation.date == latest_alloc_date,
            )
            .all()
        )
        w = [float(a.weight) for a in allocs if a.weight is not None]
        total_w = sum(w)
        if total_w > 0 and len(w) > 0:
            norm = [x / total_w for x in w]
            country_hhi = sum(x * x for x in norm) * 10_000
            geo_div = 1.0 - country_hhi / 10_000

    return {
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "cvar": round(cvar_ann * 100, 2),       # as percentage (e.g. -25.3)
        "hhi": round(hhi, 1),
        "effective_n": round(effective_n, 1),
        "geo_div": round(geo_div, 4),
        "hit_ratio": round(hit_ratio, 4),
        "max_underwater": max_underwater,
        # Extra display fields
        "ann_return_pct": round(ann_return * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "num_holdings": num_holdings,
        "data_points": n,
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
    rf_annual: float = 0.04,
    etf_ids: Optional[List[UUID]] = None,
) -> List[Dict]:
    """
    Compute GoETF Score for all ETFs (or a UUID-filtered subset).
    Returns list sorted by score descending (None scores last).
    """
    query = db.query(ETF)
    if etf_ids:
        query = query.filter(ETF.id.in_(etf_ids))
    etfs = query.order_by(ETF.ticker).all()

    # Step 1: raw metrics per ETF
    rows = []
    for etf in etfs:
        raw = _compute_raw_metrics(db, etf, rf_annual)
        rows.append({"etf_id": str(etf.id), "ticker": etf.ticker, "name": etf.name, "metrics": raw})

    # Step 2: score each ETF against fixed absolute reference ranges
    results = []
    for row in rows:
        if row["metrics"] is None:
            results.append(
                {
                    "etf_id": row["etf_id"],
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "goetf_score": None,
                    "insufficient_data": True,
                }
            )
            continue

        metric_scores = {
            m: _absolute_score(m, row["metrics"][m])
            for m in SCORE_WEIGHTS
        }
        raw_score = sum(SCORE_WEIGHTS[m] * metric_scores[m] for m in SCORE_WEIGHTS)
        goetf_score = round(1.0 + raw_score * 9.0, 1)

        results.append(
            {
                "etf_id": row["etf_id"],
                "ticker": row["ticker"],
                "name": row["name"],
                "goetf_score": goetf_score,
                **row["metrics"],
                "metric_scores": {m: round(metric_scores[m], 3) for m in metric_scores},
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
    rf_annual: float = 0.04,
) -> Dict:
    """
    GoETF Portfolio Score.
      base          = Σ w_i * goetf_score_i
      overlap_penalty = weighted avg pairwise weight_overlap * 2  (max 2 pts)
      allocation_bonus= max(0, portfolio_geo_div − avg_individual_geo_div)  (0–1 pt)
      final         = clamp(base − penalty + bonus, 1, 10)
    Also computes a single-swap improvement tip.
    """
    from app.services.analytics_service import AnalyticsService

    active = [p for p in portfolio if p.get("weight", 0) > 0 and p.get("etf_id")]
    if not active:
        return {"error": "No valid ETFs in portfolio"}

    total_w = sum(p["weight"] for p in active)

    # All ETF scores (universe for tip generation)
    all_scores = compute_goetf_scores(db, rf_annual)
    score_map = {s["etf_id"]: s.get("goetf_score") or 5.0 for s in all_scores}
    geo_map = {s["etf_id"]: s.get("geo_div", 0.5) for s in all_scores}
    ticker_map = {s["etf_id"]: s["ticker"] for s in all_scores}

    # 1. Base score
    base = sum((p["weight"] / total_w) * score_map.get(p["etf_id"], 5.0) for p in active)

    # 2. Pairwise weight overlaps
    etf_uuids = [UUID(p["etf_id"]) for p in active]
    weights_norm = [p["weight"] / total_w for p in active]
    pairwise_overlaps = []

    for i in range(len(etf_uuids)):
        for j in range(i + 1, len(etf_uuids)):
            ov_result = AnalyticsService.calculate_overlap(db, [etf_uuids[i], etf_uuids[j]])
            weight_ov = 0.0
            if "matrix" in ov_result:
                for v in ov_result["matrix"].values():
                    weight_ov = v.get("weight_overlap", 0)
            combined_w = (weights_norm[i] + weights_norm[j]) / 2
            pairwise_overlaps.append(
                {
                    "etf_a_id": str(etf_uuids[i]),
                    "etf_b_id": str(etf_uuids[j]),
                    "etf_a_ticker": ticker_map.get(str(etf_uuids[i]), active[i]["etf_id"]),
                    "etf_b_ticker": ticker_map.get(str(etf_uuids[j]), active[j]["etf_id"]),
                    "weight_overlap_pct": round(float(weight_ov), 1),
                    "combined_weight_pct": round(combined_w * 100, 1),
                }
            )

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
            norm_c = [v / total_c for v in country_vals]
            port_country_hhi = sum(x * x for x in norm_c) * 10_000
            portfolio_geo_div = round(1.0 - port_country_hhi / 10_000, 3)
            avg_ind_geo = sum(
                (p["weight"] / total_w) * geo_map.get(p["etf_id"], 0.5) for p in active
            )
            allocation_bonus = max(0.0, portfolio_geo_div - avg_ind_geo)

    final_score = max(1.0, min(10.0, base - overlap_penalty + allocation_bonus))

    # 4. Tip
    tip = _compute_tip(db, active, total_w, rf_annual, all_scores, score_map, geo_map, ticker_map, final_score)

    # Build individual scores list
    active_ids = {p["etf_id"] for p in active}
    individual_scores = []
    for s in all_scores:
        if s["etf_id"] in active_ids:
            p = next(p for p in active if p["etf_id"] == s["etf_id"])
            individual_scores.append(
                {
                    "etf_id": s["etf_id"],
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "goetf_score": s.get("goetf_score"),
                    "weight_pct": round(p["weight"] / total_w * 100, 1),
                }
            )

    return {
        "portfolio_score": round(final_score, 1),
        "base_score": round(base, 1),
        "overlap_penalty": round(overlap_penalty, 2),
        "allocation_bonus": round(allocation_bonus, 2),
        "avg_overlap_pct": round(avg_overlap_pct, 1),
        "portfolio_geo_div": portfolio_geo_div,
        "pairwise_overlaps": pairwise_overlaps,
        "individual_scores": individual_scores,
        "tip": tip,
    }


# ---------------------------------------------------------------------------
# Tip computation: try single-ETF swaps
# ---------------------------------------------------------------------------
def _compute_tip(
    db: Session,
    active: List[Dict],
    total_w: float,
    rf_annual: float,
    all_scores: List[Dict],
    score_map: Dict[str, float],
    geo_map: Dict[str, float],
    ticker_map: Dict[str, str],
    current_score: float,
) -> Optional[Dict]:
    """
    Try replacing each ETF with each alternative from the universe.
    Return the single swap that most improves the portfolio score.
    Only considers swaps with improvement > 0.1 points.
    """
    from app.services.analytics_service import AnalyticsService

    portfolio_ids = {p["etf_id"] for p in active}
    # Candidates: ETFs not already in portfolio with valid scores
    alternatives = [
        s for s in all_scores
        if s["etf_id"] not in portfolio_ids and s.get("goetf_score") is not None
    ]

    if not alternatives or len(active) < 2:
        return None

    best_score = current_score + 0.1  # minimum improvement threshold
    best_tip = None

    for i, item in enumerate(active):
        for alt in alternatives:
            # Build candidate portfolio with the swap
            candidate = [
                {"etf_id": alt["etf_id"] if j == i else p["etf_id"], "weight": p["weight"]}
                for j, p in enumerate(active)
            ]
            cand_total_w = sum(p["weight"] for p in candidate)

            # Base score
            cand_base = sum(
                (p["weight"] / cand_total_w) * score_map.get(p["etf_id"], 5.0)
                for p in candidate
            )

            # Pairwise overlaps for candidate
            cand_ids = [UUID(p["etf_id"]) for p in candidate]
            cand_w_norms = [p["weight"] / cand_total_w for p in candidate]
            ov_list = []
            for a in range(len(cand_ids)):
                for b in range(a + 1, len(cand_ids)):
                    ov = AnalyticsService.calculate_overlap(db, [cand_ids[a], cand_ids[b]])
                    weight_ov = 0.0
                    if "matrix" in ov:
                        for v in ov["matrix"].values():
                            weight_ov = v.get("weight_overlap", 0)
                    combined_w = (cand_w_norms[a] + cand_w_norms[b]) / 2 * 100
                    ov_list.append((float(weight_ov), combined_w))

            if ov_list:
                total_cw = sum(o[1] for o in ov_list)
                cand_avg_ov = sum(o[0] * o[1] for o in ov_list) / total_cw if total_cw > 0 else 0
            else:
                cand_avg_ov = 0.0
            cand_penalty = (cand_avg_ov / 100) * 2.0

            # Simplified allocation bonus: compare candidate avg geo_div vs current
            cand_avg_geo = sum(
                (p["weight"] / cand_total_w) * geo_map.get(p["etf_id"], 0.5) for p in candidate
            )
            curr_avg_geo = sum(
                (p["weight"] / total_w) * geo_map.get(p["etf_id"], 0.5) for p in active
            )
            cand_bonus = max(0.0, cand_avg_geo - curr_avg_geo)

            cand_score = max(1.0, min(10.0, cand_base - cand_penalty + cand_bonus))

            if cand_score > best_score:
                best_score = cand_score
                old_ticker = ticker_map.get(item["etf_id"], item["etf_id"])
                new_ticker = alt["ticker"]
                best_tip = {
                    "replace_etf_id": item["etf_id"],
                    "replace_ticker": old_ticker,
                    "with_etf_id": alt["etf_id"],
                    "with_ticker": new_ticker,
                    "new_score": round(best_score, 1),
                    "improvement": round(best_score - current_score, 1),
                    "reason": (
                        f"Replacing {old_ticker} with {new_ticker} reduces holdings overlap "
                        f"and improves portfolio diversification."
                    ),
                }

    return best_tip
