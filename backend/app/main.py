import os
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db, init_db
from app.models import HealthResponse
from app.api.routes import etfs, analytics, admin
from app.core.auth import verify_api_key
from app.schemas import APIKey

app = FastAPI(
    title="ETF Analytics API",
    description="REST API für ETF-Datenanalyse",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()
    print("✓ Database initialized")

@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy",
        database=db_status,
        timestamp=datetime.utcnow()
    )

@app.get("/")
async def root():
    return {
        "message": "ETF Analytics API",
        "version": "1.0.0",
        "docs": "/docs"
    }

app.include_router(etfs.router)
app.include_router(analytics.router)
app.include_router(admin.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
