import asyncio

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_google_account_for_session, hash_api_key, verify_api_key
from app.api.routes import auth
from app.schemas import APIKey, Base, GoogleAccount, WebSession


@pytest.fixture
def auth_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[
        APIKey.__table__,
        GoogleAccount.__table__,
        WebSession.__table__,
    ])
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_verified_google_claims_are_normalized(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    verified = {}

    def fake_verify(credential, request, client_id):
        verified.update(credential=credential, client_id=client_id)
        return {
            "sub": "google-user-id",
            "email": "User@Example.com",
            "email_verified": True,
            "name": "  Example User  ",
        }

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", fake_verify)

    claims = auth._verified_google_claims("google-id-token")

    assert verified == {"credential": "google-id-token", "client_id": "client-id"}
    assert claims == {
        "google_sub": "google-user-id",
        "email": "user@example.com",
        "name": "Example User",
    }


def test_google_sign_in_requires_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        auth._verified_google_claims("google-id-token")

    assert exc_info.value.status_code == 503


def test_google_sign_in_rejects_unverified_email(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(
        auth.id_token,
        "verify_oauth2_token",
        lambda *_args: {
            "sub": "google-user-id",
            "email": "user@example.com",
            "email_verified": False,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        auth._verified_google_claims("google-id-token")

    assert exc_info.value.status_code == 401


def test_google_session_authenticates_and_can_be_revoked(
    auth_db,
    monkeypatch,
):
    db = auth_db
    monkeypatch.setattr(
        auth,
        "_verified_google_claims",
        lambda _credential: {
            "google_sub": "google-user-id",
            "email": "user@example.com",
            "name": "Example User",
        },
    )
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    sent_emails = []
    monkeypatch.setattr(
        auth,
        "send_api_key_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )
    response = Response()

    result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        response,
        db,
    )

    cookie_header = response.headers["set-cookie"].lower()
    session_token = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert result["email"] == "user@example.com"
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=none" in cookie_header
    assert result["has_api_key"] is True
    assert result["api_key_emailed"] is True
    assert len(sent_emails) == 1
    stored_key = db.query(APIKey).one()
    assert stored_key.key == hash_api_key(sent_emails[0]["api_key"])
    assert auth.get_web_session(session_token, db)["email"] == "user@example.com"
    assert auth.get_web_session(session_token, db)["has_api_key"] is True
    authenticated_user = asyncio.run(
        verify_api_key(x_api_key=None, web_session=session_token, db=db)
    )
    assert authenticated_user.email == "user@example.com"

    second_result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        Response(),
        db,
    )
    assert second_result["has_api_key"] is True
    assert second_result["api_key_emailed"] is False
    assert len(sent_emails) == 1
    assert db.query(APIKey).one().key == stored_key.key

    stored_session = db.query(WebSession).filter(
        WebSession.token_hash == hash_api_key(session_token)
    ).one()
    assert stored_session.token_hash == hash_api_key(session_token)
    assert stored_session.token_hash != session_token

    auth.logout_google_session(Response(), session_token, db)
    assert get_google_account_for_session(session_token, db) is None


def test_google_sign_in_preserves_an_existing_api_key(auth_db, monkeypatch):
    db = auth_db
    existing_key_hash = hash_api_key("existing-api-key")
    db.add(APIKey(
        key=existing_key_hash,
        name="user",
        email="user@example.com",
        rate_limit_per_minute=60,
        is_active=True,
    ))
    db.commit()
    sent_emails = []
    monkeypatch.setattr(
        auth,
        "_verified_google_claims",
        lambda _credential: {
            "google_sub": "google-user-id",
            "email": "user@example.com",
            "name": "Example User",
        },
    )
    monkeypatch.setattr(
        auth,
        "send_api_key_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )

    result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        Response(),
        db,
    )

    assert result["has_api_key"] is True
    assert result["api_key_emailed"] is False
    assert sent_emails == []
    assert db.query(APIKey).one().key == existing_key_hash


def test_google_session_remains_active_when_key_email_fails(auth_db, monkeypatch):
    db = auth_db
    monkeypatch.setattr(
        auth,
        "_verified_google_claims",
        lambda _credential: {
            "google_sub": "google-user-id",
            "email": "user@example.com",
            "name": "Example User",
        },
    )

    def fail_email_delivery(**_kwargs):
        raise RuntimeError("Email is not configured.")

    monkeypatch.setattr(auth, "send_api_key_email", fail_email_delivery)
    response = Response()

    result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        response,
        db,
    )

    assert result["has_api_key"] is False
    assert result["api_key_emailed"] is False
    assert result["api_key_email_error"]
    assert db.query(APIKey).count() == 0
    session_token = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert auth.get_web_session(session_token, db)["email"] == "user@example.com"
