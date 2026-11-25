import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import (
    get_email_session,
    get_google_account_for_session,
    hash_api_key,
    verify_api_key,
)
from app.api.routes import admin
from app.api.routes import auth
from app.core import email as email_service
from app.schemas import (
    APIKey,
    Base,
    EmailWebSession,
    GoogleAccount,
    PendingKeyRequest,
    Settings,
    WebSession,
)


@pytest.fixture
def auth_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[
        APIKey.__table__,
        EmailWebSession.__table__,
        GoogleAccount.__table__,
        PendingKeyRequest.__table__,
        Settings.__table__,
        WebSession.__table__,
    ])
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("frontend_url", "configured_api_url", "expected_api_url"),
    [
        (
            "https://trueetf.com",
            "https://etfdata-production.up.railway.app",
            "https://api.trueetf.com",
        ),
        (
            "https://www.goetf.ch",
            "",
            "https://api.goetf.ch",
        ),
    ],
)
def test_confirmation_api_base_url_uses_brand_domain(
    monkeypatch,
    frontend_url,
    configured_api_url,
    expected_api_url,
):
    monkeypatch.setenv("FRONTEND_URL", frontend_url)
    monkeypatch.setenv("API_BASE_URL", configured_api_url)

    assert auth._confirmation_api_base_url() == expected_api_url


def test_admin_routes_accept_admin_api_key_and_reject_regular_key(auth_db):
    db = auth_db
    admin_account = GoogleAccount(
        google_sub="google-admin-id",
        email="stefan.heinecke1@gmail.com",
        name="Admin User",
    )
    db.add(admin_account)
    db.flush()
    admin_session_token = "admin-web-session"
    db.add_all([
        APIKey(
            key=hash_api_key("admin-key"),
            name="admin",
            email="stefan.heinecke1@gmail.com",
            is_active=True,
            is_admin=True,
        ),
        APIKey(
            key=hash_api_key("regular-key"),
            name="regular",
            email="user@example.com",
            is_active=True,
            is_admin=False,
        ),
        WebSession(
            google_account_id=admin_account.id,
            token_hash=hash_api_key(admin_session_token),
            expires_at=datetime.utcnow() + timedelta(days=1),
        ),
    ])
    db.commit()

    asyncio.run(admin.verify_admin_access(None, None, admin_session_token, db))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(admin.verify_admin_access(None, "regular-key", None, db))
    assert exc_info.value.status_code == 403


def test_admin_routes_keep_service_secret_authentication(auth_db, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "worker-secret")

    asyncio.run(admin.verify_admin_access("worker-secret", None, None, auth_db))


def test_new_user_notification_uses_resend_and_configured_recipient(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "noreply@example.com")
    requests = []

    class SuccessfulResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        requests.append((url, kwargs))
        return SuccessfulResponse()

    monkeypatch.setattr(email_service._requests, "post", fake_post)

    email_service.send_new_user_notification_email(
        to_email="contact@example.com",
        user_email="new-user@example.com",
        registration_method="Google",
    )

    assert len(requests) == 1
    url, request = requests[0]
    assert url == "https://api.resend.com/emails"
    assert request["json"]["to"] == ["contact@example.com"]
    assert request["json"]["from"] == "noreply@example.com"
    assert request["json"]["subject"] == "New TrueETF user registration"
    assert "new-user@example.com" in request["json"]["text"]
    assert request["timeout"] == 10


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
    db.add(Settings(key="contact_email", value="owner@example.com"))
    db.commit()
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
    registration_notifications = []
    monkeypatch.setattr(
        auth,
        "send_api_key_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )
    monkeypatch.setattr(
        auth,
        "send_new_user_notification_email",
        lambda **kwargs: registration_notifications.append(kwargs),
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
    assert result["is_admin"] is False
    assert result["api_key_emailed"] is True
    assert len(sent_emails) == 1
    assert registration_notifications == [{
        "to_email": "owner@example.com",
        "user_email": "user@example.com",
        "registration_method": "Google",
    }]
    stored_key = db.query(APIKey).one()
    assert stored_key.key == hash_api_key(sent_emails[0]["api_key"])
    assert stored_key.is_admin is False
    authenticated_user = asyncio.run(
        verify_api_key(x_api_key=None, web_session=session_token, db=db)
    )
    assert authenticated_user.email == "user@example.com"
    session_data = auth.get_web_session(api_key=authenticated_user, db=db)
    assert session_data["email"] == "user@example.com"
    assert session_data["has_api_key"] is True

    second_result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        Response(),
        db,
    )
    assert second_result["has_api_key"] is True
    assert second_result["api_key_emailed"] is False
    assert len(sent_emails) == 1
    assert len(registration_notifications) == 1
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


def test_default_admin_email_is_stored_as_admin_on_google_key(
    auth_db,
    monkeypatch,
):
    db = auth_db
    monkeypatch.setattr(
        auth,
        "_verified_google_claims",
        lambda _credential: {
            "google_sub": "google-admin-id",
            "email": "Stefan.Heinecke1@gmail.com",
            "name": "Stefan Heinecke",
        },
    )
    monkeypatch.setattr(auth, "send_api_key_email", lambda **_kwargs: None)
    response = Response()

    result = auth.google_session(
        auth.GoogleLoginRequest(credential="google-id-token"),
        response,
        db,
    )

    stored_key = db.query(APIKey).one()
    session_token = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    authenticated_user = asyncio.run(
        verify_api_key(x_api_key=None, web_session=session_token, db=db)
    )

    assert result["is_admin"] is True
    assert stored_key.is_admin is True
    assert auth.get_web_session(api_key=authenticated_user, db=db)["is_admin"] is True


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
    authenticated_user = asyncio.run(
        verify_api_key(x_api_key=None, web_session=session_token, db=db)
    )
    assert auth.get_web_session(api_key=authenticated_user, db=db)["email"] == "user@example.com"


def test_email_request_keeps_new_key_inactive_until_confirmation(
    auth_db,
    monkeypatch,
):
    db = auth_db
    db.add(Settings(key="contact_email", value="owner@example.com"))
    db.commit()
    sent_confirmations = []
    registration_notifications = []
    monkeypatch.setattr(
        auth,
        "send_confirmation_email",
        lambda **kwargs: sent_confirmations.append(kwargs),
    )
    monkeypatch.setattr(
        auth,
        "send_new_user_notification_email",
        lambda **kwargs: registration_notifications.append(kwargs),
    )
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    request_response = Response()
    result = auth.request_key("User@Example.com", request_response, db)

    raw_key = sent_confirmations[0]["api_key"]
    token = sent_confirmations[0]["confirm_url"].rsplit("token=", 1)[1]
    browser_token = request_response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    key_record = db.query(APIKey).one()
    assert result["email"] == "user@example.com"
    assert result["has_active_key"] is False
    assert "pending_email_session" in request_response.headers["set-cookie"]
    assert key_record.key == hash_api_key(raw_key)
    assert key_record.is_active is False
    assert db.query(PendingKeyRequest).count() == 1
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(x_api_key=raw_key, web_session=None, db=db))
    assert exc_info.value.status_code == 401
    assert auth.email_confirmation_status(
        Response(), browser_token, None, db
    ) == {"pending": True, "authenticated": False}
    assert registration_notifications == []

    phone_response = auth.confirm_key(token, None, db)

    assert registration_notifications == [{
        "to_email": "owner@example.com",
        "user_email": "user@example.com",
        "registration_method": "Email",
    }]
    cookie_header = phone_response.headers["set-cookie"].lower()
    phone_session_token = phone_response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert phone_response.status_code == 200
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=none" in cookie_header
    assert "https://app.example.com" in phone_response.body.decode()
    assert db.query(APIKey).one().key == hash_api_key(raw_key)
    assert db.query(APIKey).one().is_active is True
    assert db.query(PendingKeyRequest).one().confirmed_at is not None
    assert get_email_session(phone_session_token, db).email == "user@example.com"

    first_device_response = Response()
    status = auth.email_confirmation_status(
        first_device_response,
        browser_token,
        None,
        db,
    )
    assert status["authenticated"] is True
    assert status["email"] == "user@example.com"
    assert db.query(PendingKeyRequest).count() == 0
    session_cookie = next(
        value for value in first_device_response.headers.getlist("set-cookie")
        if value.startswith("web_session=")
    )
    session_token = session_cookie.split(";", 1)[0].split("=", 1)[1]

    authenticated_user = asyncio.run(
        verify_api_key(
            x_api_key="previous-invalid-key",
            web_session=session_token,
            db=db,
        )
    )
    assert authenticated_user.email == "user@example.com"
    session_data = auth.get_web_session(api_key=authenticated_user, db=db)
    assert session_data["has_api_key"] is True
    assert session_data["email"] == "user@example.com"

    db.query(APIKey).one().is_active = False
    db.commit()
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            verify_api_key(x_api_key=None, web_session=session_token, db=db)
        )
    assert exc_info.value.status_code == 401

    auth.logout_google_session(Response(), session_token, db)
    assert get_email_session(session_token, db) is None


def test_email_confirmation_preserves_an_existing_active_key(
    auth_db,
    monkeypatch,
):
    db = auth_db
    key_hash = hash_api_key("existing-api-key")
    db.add(APIKey(
        key=key_hash,
        name="user",
        email="user@example.com",
        rate_limit_per_minute=60,
        is_active=True,
    ))
    existing_session_token = "existing-email-session"
    db.add(EmailWebSession(
        email="user@example.com",
        token_hash=hash_api_key(existing_session_token),
        expires_at=datetime.utcnow() + timedelta(days=7),
    ))
    db.commit()
    sent_confirmations = []
    monkeypatch.setattr(
        auth,
        "send_confirmation_email",
        lambda **kwargs: sent_confirmations.append(kwargs),
    )

    request_response = Response()
    result = auth.request_key("user@example.com", request_response, db)

    assert result["has_active_key"] is True
    assert sent_confirmations[0]["has_active_key"] is True
    assert sent_confirmations[0]["api_key"] is None
    assert db.query(APIKey).one().key == key_hash
    browser_token = request_response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert auth.email_confirmation_status(
        Response(),
        browser_token,
        existing_session_token,
        db,
    ) == {"pending": True, "authenticated": False}

    token = sent_confirmations[0]["confirm_url"].rsplit("token=", 1)[1]
    response = auth.confirm_key(token, None, db)
    session_token = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    authenticated_user = asyncio.run(
        verify_api_key(x_api_key=None, web_session=session_token, db=db)
    )
    assert authenticated_user.email == "user@example.com"
    assert db.query(APIKey).one().key == key_hash
    assert db.query(APIKey).one().is_active is True


def test_email_request_failure_does_not_create_inactive_key(
    auth_db,
    monkeypatch,
):
    db = auth_db
    def fail_email_delivery(**_kwargs):
        raise RuntimeError("Email is not configured.")

    monkeypatch.setattr(auth, "send_confirmation_email", fail_email_delivery)
    with pytest.raises(HTTPException) as exc_info:
        auth.request_key("user@example.com", Response(), db)

    assert exc_info.value.status_code == 503
    assert db.query(APIKey).count() == 0
    assert db.query(PendingKeyRequest).count() == 0
