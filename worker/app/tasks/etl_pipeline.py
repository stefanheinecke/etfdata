import logging
import os
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from app.schemas import ETLJob

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")

class ETLPipeline:
    def __init__(self, db: Session):
        self.db = db

    def run_etl_job(self, job_name: str):
        job = ETLJob(
            job_name=job_name,
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()

        try:
            logger.info(f"Starting ETL job: {job_name}")

            if job_name == "daily_etf_import":
                records = self._import_etf_data()
            elif job_name == "daily_holdings_import":
                records = self._import_holdings_data()
            elif job_name == "daily_allocations_import":
                records = self._import_allocations_data()
            else:
                records = 0

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.records_processed = records

            logger.info(f"ETL job {job_name} completed with {records} records")

        except Exception as e:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            logger.error(f"ETL job {job_name} failed: {str(e)}")

        self.db.commit()
        return job

    def _import_etf_data(self) -> int:
        """Call backend /admin/refresh-prices to upsert latest closing prices."""
        resp = requests.post(
            f"{BACKEND_URL}/admin/refresh-prices",
            headers={"x-admin-secret": ADMIN_SECRET},
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("total_rows_upserted", 0)
        errors = data.get("errors", [])
        if errors:
            logger.warning("refresh-prices reported errors: %s", errors)
        logger.info("refresh-prices: %d rows upserted across %d ETFs",
                    rows, len(data.get("etfs", [])))
        return rows

    def _import_holdings_data(self) -> int:
        # Holdings change monthly — not implemented for daily refresh
        return 0

    def _import_allocations_data(self) -> int:
        # Allocations change monthly — not implemented for daily refresh
        return 0
