import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.db.database import SessionLocal
from app.tasks.data_generator import seed_database
from app.tasks.etl_pipeline import ETLPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_etl_jobs():
    db = SessionLocal()
    try:
        pipeline = ETLPipeline(db)
        pipeline.run_etl_job("daily_etf_import")
        pipeline.run_etl_job("daily_holdings_import")
        pipeline.run_etl_job("daily_allocations_import")
    finally:
        db.close()

def seed_data_once():
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

def start_scheduler():
    db = SessionLocal()

    try:
        logger.info("Checking if database needs seeding...")
        from app.schemas import Base, ETF
        Base.metadata.create_all(bind=__import__('sqlalchemy').create_engine(
            __import__('os').getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/etfdata")
        ))

        etf_count = db.query(ETF).count()
        if etf_count == 0:
            logger.info("Database empty, seeding with sample data...")
            seed_database(db)
    finally:
        db.close()

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        run_etl_jobs,
        trigger=CronTrigger(hour=2, minute=0),
        id='daily_etl',
        name='Daily ETL Jobs',
        replace_existing=True
    )

    scheduler.start()
    logger.info("ETL Scheduler started")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
