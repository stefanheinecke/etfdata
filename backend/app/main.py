import os
import time
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db, init_db, SessionLocal
from app.models import HealthResponse
from app.api.routes import etfs, analytics, admin, auth
from app.core.auth import verify_api_key, hash_api_key
from app.schemas import APIKey, RequestLog

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
_SKIP_LOG_PATHS = {"/health", "/"}

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        # Buffer JSON bodies only; skip multipart/form-data to avoid stream corruption
        body_str = None
        content_type = request.headers.get("content-type", "")
        if request.method in ("POST", "PUT", "PATCH") and "application/json" in content_type:
            body_bytes = await request.body()
            if body_bytes:
                body_str = body_bytes[:4096].decode("utf-8", errors="replace")

        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if request.url.path not in _SKIP_LOG_PATHS:
            try:
                api_key_header = request.headers.get("x-api-key")
                api_key_id = None
                api_key_name = None
                email = None
                if api_key_header:
                    hashed = hash_api_key(api_key_header)
                    db_log = SessionLocal()
                    try:
                        key_obj = db_log.query(APIKey).filter(APIKey.key == hashed).first()
                        if key_obj:
                            api_key_id = key_obj.id
                            api_key_name = key_obj.name
                            email = key_obj.email
                    finally:
                        db_log.close()

                db_log = SessionLocal()
                try:
                    log = RequestLog(
                        api_key_id=api_key_id,
                        api_key_name=api_key_name,
                        email=email,
                        method=request.method,
                        path=request.url.path,
                        query_string=str(request.url.query) or None,
                        request_body=body_str,
                        status_code=response.status_code,
                        response_time_ms=elapsed_ms,
                        client_ip=request.client.host if request.client else None,
                    )
                    db_log.add(log)
                    db_log.commit()
                finally:
                    db_log.close()
            except Exception:
                pass  # never break the response on logging errors

        return response

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
app.add_middleware(RequestLogMiddleware)

@app.on_event("startup")
async def startup():
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database init failed: {e}")
        raise

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
app.include_router(auth.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
