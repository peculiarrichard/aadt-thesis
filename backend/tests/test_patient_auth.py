"""Email+password sign-in for simulated patients -- mirrors
test_google_auth.py's shape, but there's no external provider to mock here.
Requires a live database (`docker compose up -d`) with the patient-facing
migration applied; skips if the database is unreachable.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.db.models import Patient
from backend.db.session import SessionLocal
from backend.main import app

client = TestClient(app)


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
def cleanup_patients(require_db: None):
    del require_db
    emails: list[str] = []
    yield emails
    cleanup = SessionLocal()
    for email in emails:
        cleanup.execute(delete(Patient).where(Patient.email == email))
    cleanup.commit()
    cleanup.close()


def _unique_email() -> str:
    return f"patient-{uuid.uuid4().hex[:8]}@example.com"


def test_signup_creates_a_patient_and_establishes_a_session(cleanup_patients: list[str]):
    email = _unique_email()
    cleanup_patients.append(email)

    response = client.post(
        "/auth/patient/signup",
        json={
            "email": email,
            "password": "sim-password",
            "username": f"sim-{uuid.uuid4().hex[:6]}",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email

    me_response = client.get("/auth/patient/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email


def test_signup_rejects_a_duplicate_email(cleanup_patients: list[str]):
    email = _unique_email()
    cleanup_patients.append(email)
    username = f"sim-{uuid.uuid4().hex[:6]}"

    first = client.post(
        "/auth/patient/signup", json={"email": email, "password": "pw", "username": username}
    )
    assert first.status_code == 200

    second = client.post(
        "/auth/patient/signup",
        json={"email": email, "password": "pw", "username": f"sim-{uuid.uuid4().hex[:6]}"},
    )
    assert second.status_code == 400


def test_login_rejects_wrong_password(cleanup_patients: list[str]):
    email = _unique_email()
    cleanup_patients.append(email)
    client.post(
        "/auth/patient/signup",
        json={"email": email, "password": "correct", "username": f"sim-{uuid.uuid4().hex[:6]}"},
    )

    response = client.post("/auth/patient/login", json={"email": email, "password": "wrong"})

    assert response.status_code == 401


def test_login_succeeds_with_correct_password(cleanup_patients: list[str]):
    email = _unique_email()
    cleanup_patients.append(email)
    client.post(
        "/auth/patient/signup",
        json={"email": email, "password": "correct", "username": f"sim-{uuid.uuid4().hex[:6]}"},
    )
    client.post("/auth/patient/logout")

    response = client.post("/auth/patient/login", json={"email": email, "password": "correct"})

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_requires_a_session(require_db: None):
    del require_db
    fresh_client = TestClient(app)

    response = fresh_client.get("/auth/patient/me")

    assert response.status_code == 401
