from datetime import date
from typing import List, Dict
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.schemas import Holding, Allocation, ETF

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
            # Only include real ISINs (12 chars, 2-letter country prefix) in overlap
            # comparison.  Ticker-based identifiers (e.g. "TRU") are exchange-scoped
            # and the same ticker can refer to different companies on different
            # exchanges, causing false positives.
            holdings_data[str(etf_id)] = {
                h.instrument_isin: float(h.weight)
                for h in holdings
                if len(h.instrument_isin) == 12 and h.instrument_isin[:2].isalpha()
            }

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
