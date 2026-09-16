"""
AI ETF Explainer
Generates a plain-English explanation of a single ETF, strictly grounded in
this ETF's own data already stored in the DB (metadata, holdings, allocations,
GoETF Quality Score). No external knowledge about the fund/issuer is used —
the LLM is instructed to rely only on the facts assembled below.

Results are cached per ETF in the etf_explanations table and only regenerated
on demand (force=True), since each generation costs an LLM API call.
"""
import os
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.schemas import ETF, ETFExplanation
from app.services.asset_classes import equity_analytics_supported, normalize_asset_class
from app.services.analytics_service import _holdings_snapshot, _allocation_snapshot
from app.services.scoring_service import compute_goetf_scores

OPENAI_MODEL = os.getenv("OPENAI_EXPLAIN_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are an assistant that explains ETFs (exchange-traded funds) to retail \
investors. You will be given a structured set of facts about ONE specific ETF, pulled directly \
from a database. Rules you MUST follow:
1. Use ONLY the facts provided below. Do not use any prior knowledge about this fund, its issuer, \
or general market conditions.
2. Do not invent, estimate, or infer any number that is not present in the data.
3. If a fact needed to answer something is missing or marked unavailable, say so explicitly \
instead of guessing.
4. Do not give investment advice or a buy/sell/hold recommendation.
5. Write 3-5 short, plain-English paragraphs suitable for a retail investor: what the fund is, \
what it holds and how concentrated/diversified it is, its cost and size, and what its GoETF \
Quality Score reflects.
"""


def _format_pct(value: Optional[float]) -> str:
    return f"{value * 100:.1f}%" if value is not None else "unavailable"


def _format_usd(value: Optional[float]) -> str:
    if value is None:
        return "unavailable"
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _top_buckets(snapshot: Dict, limit: int = 10) -> str:
    if snapshot["status"] != "available":
        return f"unavailable ({snapshot.get('reason') or 'no data'})"
    items = sorted(snapshot["weights"].items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return "\n".join(f"  - {bucket}: {weight:.1f}%" for bucket, weight in items) or "  (none)"


def build_etf_context(db: Session, etf: ETF) -> str:
    """Assemble a compact, structured plain-text summary of everything known
    about this ETF in the DB, to be used as grounding context for the LLM."""
    lines = [
        f"ETF name: {etf.name}",
        f"ISIN: {etf.isin}",
        f"Provider: {etf.provider or 'unavailable'}",
        f"Domicile: {etf.domicile or 'unavailable'}",
        f"Asset class: {normalize_asset_class(etf.asset_class)}",
        f"Currency: {etf.currency or 'unavailable'}",
        f"Dividend policy: {etf.dividend_policy or 'unavailable'}",
        f"Replication method: {etf.replication_method or 'unavailable'}",
        f"Benchmark/index tracked: {etf.benchmark or 'unavailable'}",
        f"TER (total expense ratio): {f'{etf.ter}%' if etf.ter is not None else 'unavailable'}",
        f"Fund size (own currency): {etf.fund_size if etf.fund_size is not None else 'unavailable'}",
    ]

    if equity_analytics_supported(etf.asset_class):
        holdings = _holdings_snapshot(db, etf.id)
        country = _allocation_snapshot(db, etf.id, "country")
        sector = _allocation_snapshot(db, etf.id, "sector")
        currency = _allocation_snapshot(db, etf.id, "currency")

        lines.append(f"\nNumber of holdings: {len(holdings['weights']) if holdings['status'] == 'available' else 'unavailable'}")
        lines.append("Top holdings by weight:")
        lines.append(_top_buckets(holdings, limit=15))
        lines.append("\nCountry allocation:")
        lines.append(_top_buckets(country, limit=10))
        lines.append("\nSector allocation:")
        lines.append(_top_buckets(sector, limit=10))
        lines.append("\nCurrency allocation:")
        lines.append(_top_buckets(currency, limit=10))
    else:
        lines.append("\nHoldings/allocation breakdown: unavailable for this asset class.")

    score_rows = compute_goetf_scores(db, etf_ids=[etf.id])
    score = score_rows[0] if score_rows else None
    if score and score.get("status") == "available":
        lines.append(f"\nGoETF Quality Score: {score['goetf_score']}/10 (1 = very poor, 10 = excellent)")
        lines.append("Score components (equally weighted, 0-1 scale before scaling to 1-10):")
        for component, comp_score in score.get("metric_scores", {}).items():
            lines.append(f"  - {component}: {comp_score}")
    else:
        reason = score.get("reason") if score else "no score data"
        lines.append(f"\nGoETF Quality Score: unavailable ({reason})")

    return "\n".join(lines)


def _load_cached(db: Session, etf_id) -> Optional[ETFExplanation]:
    return db.query(ETFExplanation).filter(ETFExplanation.etf_id == etf_id).first()


def _store(db: Session, etf_id, text: str, model: str) -> datetime:
    now = datetime.utcnow()
    row = _load_cached(db, etf_id)
    if row is None:
        row = ETFExplanation(etf_id=etf_id)
        db.add(row)
    row.text = text
    row.model = model
    row.generated_at = now
    db.commit()
    return now


def generate_etf_explanation(db: Session, etf: ETF, force: bool = False) -> Dict:
    """Return a cached explanation, or generate + cache a new one."""
    if not force:
        cached = _load_cached(db, etf.id)
        if cached is not None:
            return {"text": cached.text, "model": cached.model,
                    "generated_at": cached.generated_at.isoformat(), "cached": True}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured on the server")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    context = build_etf_context(db, etf)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Facts about this ETF:\n\n{context}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    text = response.choices[0].message.content.strip()
    generated_at = _store(db, etf.id, text, OPENAI_MODEL)
    return {"text": text, "model": OPENAI_MODEL, "generated_at": generated_at.isoformat(), "cached": False}
