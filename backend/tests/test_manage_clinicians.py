"""Tests the admin clinician-creation CLI (Phase I). Requires `docker compose
up -d`; skips otherwise."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.db.manage_clinicians import create_or_get_clinician
from backend.db.models import Clinician
from backend.db.session import SessionLocal


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
def cleanup_by_email(require_db: None):
    del require_db
    created_emails: list[str] = []
    yield created_emails

    cleanup = SessionLocal()
    for email in created_emails:
        cleanup.execute(delete(Clinician).where(Clinician.email == email))
    cleanup.commit()
    cleanup.close()


def test_creates_a_new_clinician_with_consent_granted_by_default(cleanup_by_email: list[str]):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    cleanup_by_email.append(email)
    session = SessionLocal()

    clinician = create_or_get_clinician(session, "Dr. Test Doctor", email)
    session.close()

    assert clinician.name == "Dr. Test Doctor"
    assert clinician.email == email
    assert clinician.consent_status == "granted"


def test_is_idempotent_by_email(cleanup_by_email: list[str]):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    cleanup_by_email.append(email)
    session = SessionLocal()

    first = create_or_get_clinician(session, "Dr. Test Doctor", email)
    second = create_or_get_clinician(session, "Dr. Test Doctor (different name)", email)
    session.close()

    assert first.clinician_id == second.clinician_id
    assert second.name == "Dr. Test Doctor"  # unchanged by the second call


def test_accepts_a_custom_consent_status(cleanup_by_email: list[str]):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    cleanup_by_email.append(email)
    session = SessionLocal()

    clinician = create_or_get_clinician(session, "Dr. Test Doctor", email, consent_status="pending")
    session.close()

    assert clinician.consent_status == "pending"
