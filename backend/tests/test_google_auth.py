"""Tests the Google OAuth flow with Google's own endpoints mocked -- no real
Google credentials needed. Requires a live database (`docker compose up -d`) to
persist the clinician row; skips otherwise.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.config import get_settings
from backend.db.models import Clinician
from backend.db.session import SessionLocal
from backend.main import app


@pytest.fixture
def require_db() -> None:
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")
    session.close()


@pytest.fixture
def google_oauth_configured(require_db: None):
    del require_db
    settings = get_settings()
    original_client_id = settings.google_oauth_client_id
    settings.google_oauth_client_id = "test-client-id"
    settings.google_oauth_client_secret = "test-client-secret"

    created_google_subs: list[str] = []
    yield created_google_subs

    settings.google_oauth_client_id = original_client_id
    cleanup = SessionLocal()
    for sub in created_google_subs:
        cleanup.execute(delete(Clinician).where(Clinician.google_sub == sub))
    cleanup.commit()
    cleanup.close()


def test_login_redirects_to_google_with_state(google_oauth_configured):
    del google_oauth_configured
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/google/login")

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert "state=" in response.headers["location"]


def test_login_returns_503_when_oauth_not_configured(require_db: None):
    del require_db
    settings = get_settings()
    original = settings.google_oauth_client_id
    settings.google_oauth_client_id = ""
    try:
        client = TestClient(app)
        response = client.get("/auth/google/login")
        assert response.status_code == 503
    finally:
        settings.google_oauth_client_id = original


def test_callback_creates_a_new_clinician_and_establishes_a_session(
    google_oauth_configured: list[str],
):
    google_sub = f"test-sub-{uuid.uuid4().hex[:8]}"
    google_oauth_configured.append(google_sub)

    client = TestClient(app, follow_redirects=False)
    login_response = client.get("/auth/google/login")
    state = login_response.headers["location"].split("state=")[1].split("&")[0]

    fake_token_response = MagicMock(status_code=200)
    fake_token_response.json.return_value = {"id_token": "fake.jwt.token"}
    fake_claims = {"sub": google_sub, "email": "doctor@example.com", "name": "Dr. Test"}

    with (
        patch("backend.api.google_auth.httpx.post", return_value=fake_token_response),
        patch("backend.api.google_auth.id_token.verify_oauth2_token", return_value=fake_claims),
    ):
        callback_response = client.get(
            "/auth/google/callback", params={"code": "fake-code", "state": state}
        )

    assert callback_response.status_code in (302, 307)

    me_response = client.get("/auth/google/me")
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["email"] == "doctor@example.com"
    assert body["consent_status"] == "pending"


def test_callback_claims_an_existing_unclaimed_clinician_by_email(
    google_oauth_configured: list[str],
):
    """A clinician row can exist before its owner ever logs in (the
    walkthrough-imported doctor, db/import_walkthrough_cases.py) -- her first
    login must attach to that row, not create a second, case-less one."""
    email = f"preexisting-{uuid.uuid4().hex[:8]}@example.com"
    session = SessionLocal()
    preexisting = Clinician(
        name="Consenting GP (walkthrough study)", consent_status="granted", email=email
    )
    session.add(preexisting)
    session.commit()
    preexisting_id = preexisting.clinician_id
    session.close()

    google_sub = f"test-sub-{uuid.uuid4().hex[:8]}"
    google_oauth_configured.append(google_sub)

    client = TestClient(app, follow_redirects=False)
    login_response = client.get("/auth/google/login")
    state = login_response.headers["location"].split("state=")[1].split("&")[0]

    fake_token_response = MagicMock(status_code=200)
    fake_token_response.json.return_value = {"id_token": "fake.jwt.token"}
    fake_claims = {"sub": google_sub, "email": email, "name": "Dr. Real Doctor"}

    with (
        patch("backend.api.google_auth.httpx.post", return_value=fake_token_response),
        patch("backend.api.google_auth.id_token.verify_oauth2_token", return_value=fake_claims),
    ):
        client.get("/auth/google/callback", params={"code": "fake-code", "state": state})

    me_response = client.get("/auth/google/me")
    body = me_response.json()

    assert body["clinician_id"] == str(preexisting_id)
    assert body["consent_status"] == "granted"  # preserved, not reset to "pending"


def test_callback_rejects_mismatched_state(google_oauth_configured):
    del google_oauth_configured
    client = TestClient(app, follow_redirects=False)
    client.get("/auth/google/login")

    response = client.get(
        "/auth/google/callback", params={"code": "fake-code", "state": "wrong-state"}
    )

    assert response.status_code == 400


def test_me_requires_a_session(require_db: None):
    del require_db
    client = TestClient(app)

    response = client.get("/auth/google/me")

    assert response.status_code == 401
