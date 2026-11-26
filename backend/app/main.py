import os
import time
import logging
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, text

from app.db.database import get_db, init_db, SessionLocal
from app.models import HealthResponse
from app.api.routes import etfs, analytics, admin, auth, scores
from app.core.auth import (
    get_email_session,
    get_google_account_for_session,
    hash_api_key,
    verify_api_key,
)
from app.schemas import APIKey, RequestLog

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
_SKIP_LOG_PATHS = {"/health", "/"}


def _active_api_key_for_email(db: Session, email: str):
    now = datetime.utcnow()
    return db.query(APIKey).filter(
        APIKey.email == email,
        APIKey.is_active.is_(True),
        or_(APIKey.expires_at.is_(None), APIKey.expires_at >= now),
    ).order_by(APIKey.created_at.desc()).first()


def _request_log_identity(db: Session, api_key_header: str, web_session: str):
    if web_session:
        account = get_google_account_for_session(web_session, db)
        if account:
            api_key = _active_api_key_for_email(db, account.email)
            return (
                api_key.id if api_key else None,
                api_key.name if api_key else account.name or account.email.split("@")[0],
                account.email,
            )

        email_session = get_email_session(web_session, db)
        if email_session:
            api_key = _active_api_key_for_email(db, email_session.email)
            return (
                api_key.id if api_key else None,
                api_key.name if api_key else email_session.email.split("@")[0],
                email_session.email,
            )

        legacy_key = db.query(APIKey).filter(
            APIKey.key == hash_api_key(web_session),
            APIKey.is_active.is_(True),
            or_(APIKey.expires_at.is_(None), APIKey.expires_at >= datetime.utcnow()),
        ).first()
        if legacy_key:
            return legacy_key.id, legacy_key.name, legacy_key.email

    if api_key_header:
        api_key = db.query(APIKey).filter(
            APIKey.key == hash_api_key(api_key_header)
        ).first()
        if api_key:
            return api_key.id, api_key.name, api_key.email

    return None, None, None


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        # IMPORTANT: do NOT read request.body() before call_next.
        # Doing so consumes the ASGI receive channel; downstream handlers then block
        # indefinitely waiting for body bytes that have already been drained, causing
        # a permanent hang on any endpoint that reads a JSON body (POST/PATCH/PUT).
        # Instead we read the cached _body attribute AFTER call_next — FastAPI will
        # have populated it while parsing endpoint parameters.
        try:
            response = await call_next(request)
        except Exception:
            # Catch here (inside CORSMiddleware) rather than relying on FastAPI's
            # app.exception_handler(Exception): that gets wired into Starlette's
            # ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware, so any
            # response it builds never gets CORS headers attached. Catching the
            # exception here (inside CORSMiddleware) lets the JSON response we
            # build below flow back out through CORSMiddleware normally.
            import logging
            import traceback
            logging.getLogger(__name__).error(
                "Unhandled exception on %s: %s", request.url.path, traceback.format_exc()
            )
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

        body_str = None
        content_type = request.headers.get("content-type", "")
        if (
            request.url.path != "/auth/google/session"
            and request.method in ("POST", "PUT", "PATCH")
            and "application/json" in content_type
        ):
            body_bytes = getattr(request, "_body", None)
            if body_bytes:
                body_str = body_bytes[:4096].decode("utf-8", errors="replace")
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if request.url.path not in _SKIP_LOG_PATHS:
            try:
                api_key_header = request.headers.get("x-api-key")
                db_log = SessionLocal()
                try:
                    api_key_id, api_key_name, email = _request_log_identity(
                        db_log,
                        api_key_header,
                        request.cookies.get("web_session"),
                    )
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
                logging.getLogger(__name__).exception(
                    "Could not write request log for %s %s",
                    request.method,
                    request.url.path,
                )

        return response

app = FastAPI(
    title="ETF Analytics API",
    description="REST API für ETF-Datenanalyse",
    version="1.0.0"
)

_DEFAULT_CORS_ORIGINS = (
    "https://goetf.ch",
    "https://www.goetf.ch",
    "https://trueetf.com",
    "https://www.trueetf.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(_DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Without this, an unhandled exception skips CORSMiddleware entirely and the
    # browser reports an opaque "CORS policy" / Network Error instead of the real 500.
    import logging
    import traceback
    logging.getLogger(__name__).error("Unhandled exception on %s: %s\n%s", request.url.path, exc, traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
app.include_router(scores.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
