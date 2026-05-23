import random
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session
from app.schemas import ETF, Holding, Allocation, Performance

PROVIDERS = ["Vanguard", "iShares", "UBS"]
SECTORS = [
    "Technology", "Healthcare", "Financials", "Energy", "Industrials",
    "Consumer Discretionary", "Consumer Staples", "Real Estate", "Materials", "Utilities"
]
COUNTRIES = ["US", "DE", "FR", "GB", "JP", "CH", "NL", "SE", "CA", "AU"]

ISINS = [
    "IE00B4L5Y983", "IE00B0M63284", "IE00BJ0KDQ92",
    "IE00B8GKDB10", "IE00BK1PV551", "IE00BHBXQ580",
    "IE00BOXW3913", "IE00B1FZS798", "IE00BX5RQT88",
    "IE00B0M6HP67", "IE00BD3QHZ91", "IE00BMDBMM74",
    "IE00B1BNRP29", "IE00BFXNM860", "IE00B579F325"
]


def seed_database(db: Session) -> dict:
    etf_count = _generate_etfs(db)
    holdings_count = _generate_holdings(db)
    allocations_count = _generate_allocations(db)
    performance_count = _generate_performance(db)
    return {
        "etfs": etf_count,
        "holdings": holdings_count,
        "allocations": allocations_count,
        "performance": performance_count,
    }


def _generate_etfs(db: Session) -> int:
    created = 0
    for i, isin in enumerate(ISINS):
        if db.query(ETF).filter(ETF.isin == isin).first():
            continue
        provider = random.choice(PROVIDERS)
        db.add(ETF(
            id=uuid4(),
            isin=isin,
            ticker=f"ETF{i:02d}",
            name=f"Test ETF {i + 1} ({provider})",
            provider=provider,
            domicile="IE",
            replication_method=random.choice(["Full Replication", "Sampling"]),
            ter=Decimal(str(round(random.uniform(0.03, 0.75), 2))),
            fund_size=random.randint(100_000_000, 50_000_000_000),
            benchmark="MSCI World",
            currency="EUR",
            listings={"NYSE": f"ETF{i}", "XETRA": f"ETF{i}"},
        ))
        created += 1
    db.commit()
    return created


def _generate_holdings(db: Session) -> int:
    today = date.today()
    created = 0
    for etf in db.query(ETF).all():
        if db.query(Holding).filter(Holding.etf_id == etf.id, Holding.date == today).first():
            continue
        for j in range(random.randint(20, 50)):
            db.add(Holding(
                id=uuid4(),
                etf_id=etf.id,
                date=today,
                instrument_isin=f"DE000{random.randint(100000, 999999)}",
                instrument_name=f"Stock {j + 1}",
                weight=Decimal(str(round(random.uniform(0.1, 15), 2))),
                country=random.choice(COUNTRIES),
                sector=random.choice(SECTORS),
            ))
            created += 1
    db.commit()
    return created


def _generate_allocations(db: Session) -> int:
    today = date.today()
    created = 0
    for etf in db.query(ETF).all():
        if db.query(Allocation).filter(
            Allocation.etf_id == etf.id, Allocation.date == today, Allocation.type == "sector"
        ).first():
            continue
        for sector in SECTORS:
            db.add(Allocation(id=uuid4(), etf_id=etf.id, date=today, type="sector",
                               bucket=sector, weight=Decimal(str(round(random.uniform(0, 20), 2)))))
            created += 1
        for country in COUNTRIES[:8]:
            db.add(Allocation(id=uuid4(), etf_id=etf.id, date=today, type="country",
                               bucket=country, weight=Decimal(str(round(random.uniform(0, 30), 2)))))
            created += 1
        for currency in ["EUR", "USD", "GBP", "JPY"]:
            db.add(Allocation(id=uuid4(), etf_id=etf.id, date=today, type="currency",
                               bucket=currency, weight=Decimal(str(round(random.uniform(10, 50), 2)))))
            created += 1
    db.commit()
    return created


def _generate_performance(db: Session) -> int:
    today = date.today()
    created = 0
    for etf in db.query(ETF).all():
        if db.query(Performance).filter(Performance.etf_id == etf.id, Performance.date == today).first():
            continue
        db.add(Performance(
            id=uuid4(), etf_id=etf.id, date=today,
            nav=Decimal(str(round(random.uniform(50, 500), 2))),
            close_price=Decimal(str(round(random.uniform(50, 500), 2))),
            currency="EUR",
            dividend=Decimal(str(round(random.uniform(0, 5), 2))),
        ))
        created += 1
    db.commit()
    return created
