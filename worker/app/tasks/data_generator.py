import os
import random
from datetime import datetime, date, timedelta
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

def generate_sample_etfs(db: Session, count: int = 15):
    isins = [
        "IE00B4L5Y983", "IE00B0M63284", "IE00BJ0KDQ92",
        "IE00B8GKDB10", "IE00BK1PV551", "IE00BHBXQ580",
        "IE00BOXW3913", "IE00B1FZS798", "IE00BX5RQT88",
        "IE00B0M6HP67", "IE00BD3QHZ91", "IE00BMDBMM74",
        "IE00B1BNRP29", "IE00BFXNM860", "IE00B579F325"
    ]

    for i, isin in enumerate(isins[:count]):
        existing = db.query(ETF).filter(ETF.isin == isin).first()
        if existing:
            continue

        provider = random.choice(PROVIDERS)
        etf = ETF(
            id=uuid4(),
            isin=isin,
            ticker=f"ETF{i:02d}",
            name=f"Test ETF {i+1} ({provider})",
            provider=provider,
            domicile="IE",
            replication_method=random.choice(["Full Replication", "Sampling"]),
            ter=Decimal(str(round(random.uniform(0.03, 0.75), 2))),
            fund_size=random.randint(100_000_000, 50_000_000_000),
            benchmark="MSCI World",
            currency="EUR",
            listings={"NYSE": "ETF1", "XETRA": f"ETF{i}"}
        )
        db.add(etf)

    db.commit()
    print(f"✓ Generated {count} sample ETFs")

def generate_sample_holdings(db: Session):
    etfs = db.query(ETF).all()
    today = date.today()

    for etf in etfs:
        existing = db.query(Holding).filter(
            Holding.etf_id == etf.id,
            Holding.date == today
        ).first()
        if existing:
            continue

        holdings_count = random.randint(20, 100)
        total_weight = Decimal(0)

        for j in range(holdings_count):
            weight = Decimal(str(round(random.uniform(0.1, 15), 2)))
            total_weight += weight

            holding = Holding(
                id=uuid4(),
                etf_id=etf.id,
                date=today,
                instrument_isin=f"DE000{random.randint(100000, 999999)}",
                instrument_name=f"Stock {j+1}",
                weight=weight,
                country=random.choice(COUNTRIES),
                sector=random.choice(SECTORS)
            )
            db.add(holding)

        db.commit()

    print(f"✓ Generated holdings for {len(etfs)} ETFs")

def generate_sample_allocations(db: Session):
    etfs = db.query(ETF).all()
    today = date.today()

    for etf in etfs:
        existing = db.query(Allocation).filter(
            Allocation.etf_id == etf.id,
            Allocation.date == today,
            Allocation.type == "sector"
        ).first()
        if existing:
            continue

        for sector in SECTORS:
            allocation = Allocation(
                id=uuid4(),
                etf_id=etf.id,
                date=today,
                type="sector",
                bucket=sector,
                weight=Decimal(str(round(random.uniform(0, 20), 2))))
            db.add(allocation)

        for country in COUNTRIES[:8]:
            allocation = Allocation(
                id=uuid4(),
                etf_id=etf.id,
                date=today,
                type="country",
                bucket=country,
                weight=Decimal(str(round(random.uniform(0, 30), 2))))
            db.add(allocation)

        for currency in ["EUR", "USD", "GBP", "JPY"]:
            allocation = Allocation(
                id=uuid4(),
                etf_id=etf.id,
                date=today,
                type="currency",
                bucket=currency,
                weight=Decimal(str(round(random.uniform(10, 50), 2))))
            db.add(allocation)

        db.commit()

    print(f"✓ Generated allocations for {len(etfs)} ETFs")

def generate_sample_performance(db: Session):
    etfs = db.query(ETF).all()
    today = date.today()

    for etf in etfs:
        existing = db.query(Performance).filter(
            Performance.etf_id == etf.id,
            Performance.date == today
        ).first()
        if existing:
            continue

        performance = Performance(
            id=uuid4(),
            etf_id=etf.id,
            date=today,
            nav=Decimal(str(round(random.uniform(50, 500), 2))),
            close_price=Decimal(str(round(random.uniform(50, 500), 2))),
            currency="EUR",
            dividend=Decimal(str(round(random.uniform(0, 5), 2))))
        db.add(performance)

    db.commit()
    print(f"✓ Generated performance data for {len(etfs)} ETFs")

def seed_database(db: Session):
    print("Seeding database with sample data...")
    generate_sample_etfs(db)
    generate_sample_holdings(db)
    generate_sample_allocations(db)
    generate_sample_performance(db)
    print("✓ Database seeded successfully")
