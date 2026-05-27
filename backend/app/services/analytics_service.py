from datetime import date
from typing import List, Dict
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.schemas import Holding, Allocation, ETF, Performance

class AnalyticsService:
    @staticmethod
    def calculate_overlap(db: Session, etf_ids: List[UUID], overlap_date: date = None):
        if not etf_ids or len(etf_ids) < 2:
            return {"error": "At least 2 ETFs required"}

        holdings_data = {}
        for etf_id in etf_ids:
            query = db.query(Holding).filter(Holding.etf_id == etf_id)
            if overlap_date:
                query = query.filter(Holding.date == overlap_date)
            else:
                latest_date = db.query(func.max(Holding.date)).filter(
                    Holding.etf_id == etf_id
                ).scalar()
                query = query.filter(Holding.date == latest_date)

            holdings = query.all()
            holdings_data[str(etf_id)] = {h.instrument_isin: float(h.weight) for h in holdings}

        matrix = {}
        common_holdings = []

        for i, etf_a in enumerate(etf_ids):
            for etf_b in etf_ids[i+1:]:
                etf_a_str = str(etf_a)
                etf_b_str = str(etf_b)

                holdings_a = set(holdings_data[etf_a_str].keys())
                holdings_b = set(holdings_data[etf_b_str].keys())

                common = holdings_a & holdings_b
                overlap_percent = len(common) / max(len(holdings_a), len(holdings_b)) * 100 if max(len(holdings_a), len(holdings_b)) > 0 else 0

                weight_overlap = sum(
                    min(holdings_data[etf_a_str][h], holdings_data[etf_b_str][h])
                    for h in common
                )

                key = f"{etf_a_str[:8]}_{etf_b_str[:8]}"
                matrix[key] = {
                    "etf_a": etf_a_str,
                    "etf_b": etf_b_str,
                    "common_count": len(common),
                    "overlap_percent": round(overlap_percent, 2),
                    "weight_overlap": round(float(weight_overlap), 2)
                }

                for isin in common:
                    common_holdings.append({
                        "isin": isin,
                        "etf_a_weight": round(float(holdings_data[etf_a_str][isin]), 4),
                        "etf_b_weight": round(float(holdings_data[etf_b_str][isin]), 4)
                    })

        return {"matrix": matrix, "common_holdings": common_holdings[:20]}

    @staticmethod
    def calculate_portfolio_exposure(db: Session, portfolio: List[Dict], exposure_date: date = None):
        sectors = {}
        countries = {}
        currencies = {}

        for item in portfolio:
            etf_id = item.get("etf_id")
            weight = item.get("weight", 0)

            if weight <= 0:
                continue

            etf = db.query(ETF).filter(ETF.id == etf_id).first()
            if not etf:
                continue

            query = db.query(Allocation).filter(Allocation.etf_id == etf_id)
            if exposure_date:
                query = query.filter(Allocation.date == exposure_date)
            else:
                latest_date = db.query(func.max(Allocation.date)).filter(
                    Allocation.etf_id == etf_id
                ).scalar()
                if latest_date:
                    query = query.filter(Allocation.date == latest_date)

            allocations = query.all()

            for alloc in allocations:
                alloc_weight = float(alloc.weight) * weight / 100

                if alloc.type == "sector":
                    sectors[alloc.bucket] = sectors.get(alloc.bucket, 0) + alloc_weight
                elif alloc.type == "country":
                    countries[alloc.bucket] = countries.get(alloc.bucket, 0) + alloc_weight
                elif alloc.type == "currency":
                    currencies[alloc.bucket] = currencies.get(alloc.bucket, 0) + alloc_weight

        return {
            "sectors": {k: round(v, 2) for k, v in sorted(sectors.items(), key=lambda x: x[1], reverse=True)},
            "countries": {k: round(v, 2) for k, v in sorted(countries.items(), key=lambda x: x[1], reverse=True)},
            "currencies": {k: round(v, 2) for k, v in sorted(currencies.items(), key=lambda x: x[1], reverse=True)}
        }

    @staticmethod
    def find_similar_etfs(db: Session, etf_id: UUID, top_n: int = 5):
        target_etf = db.query(ETF).filter(ETF.id == etf_id).first()
        if not target_etf:
            return {"error": "ETF not found"}

        all_etfs = db.query(ETF).filter(ETF.id != etf_id).limit(50).all()

        similarities = []

        for other_etf in all_etfs:
            overlap_result = AnalyticsService.calculate_overlap(
                db, [etf_id, other_etf.id]
            )

            if "matrix" in overlap_result and overlap_result["matrix"]:
                for overlap_data in overlap_result["matrix"].values():
                    score = overlap_data.get("overlap_percent", 0)
                    similarities.append({
                        "etf_id": str(other_etf.id),
                        "ticker": other_etf.ticker,
                        "name": other_etf.name,
                        "provider": other_etf.provider,
                        "similarity_score": round(score, 2)
                    })

        similar_etfs = sorted(similarities, key=lambda x: x["similarity_score"], reverse=True)[:top_n]

        return {"similar_etfs": similar_etfs}

    @staticmethod
    def calculate_risk_metrics(db: Session, rf_annual: float = 0.04) -> list:
        """Compute annualized volatility, Sharpe ratio, max drawdown, and HHI for every ETF."""
        import math

        etfs = db.query(ETF).order_by(ETF.ticker).all()
        results = []

        for etf in etfs:
            row: dict = {
                "etf_id":       str(etf.id),
                "ticker":       etf.ticker,
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
            prices = [float(p.close_price) for p in perf if p.close_price is not None]
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
            latest_date = (
                db.query(func.max(Holding.date))
                .filter(Holding.etf_id == etf.id)
                .scalar()
            )
            if latest_date:
                holdings = (
                    db.query(Holding)
                    .filter(Holding.etf_id == etf.id, Holding.date == latest_date)
                    .all()
                )
                weights = [float(h.weight) for h in holdings if h.weight is not None]
                total_w = sum(weights)
                row["num_holdings"] = len(weights)
                if total_w > 0:
                    normalized = [w / total_w for w in weights]
                    row["hhi"] = round(sum(w * w for w in normalized) * 10_000, 1)

            results.append(row)

        return results
