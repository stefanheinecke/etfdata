import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.db.database import SessionLocal
from app.tasks.etl_pipeline import ETLPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_etl_jobs():
    db = SessionLocal()
    try:
        pipeline = ETLPipeline(db)
        pipeline.run_etl_job("daily_etf_import")
    finally:
        db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()

    # Run once shortly after midnight UTC (markets close well before this)
    scheduler.add_job(
        run_etl_jobs,
        trigger=CronTrigger(hour=2, minute=0),
        id='daily_price_refresh',
        name='Daily ETF Price Refresh',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("ETL Scheduler started — daily price refresh at 02:00 UTC")

if __name__ == "__main__":
    start_scheduler()
