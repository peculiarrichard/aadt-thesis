"""Tests the Phase J consent model: institutional clearance (one global
setting) and per-clinician, per-subject-type, optionally per-session consent
(ConsentRegistry). Requires `docker compose up -d`; skips otherwise.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.config import get_settings
from backend.db.enums import ConsentSubjectType
from backend.db.models import Clinician, ConsentRegistry
from backend.db.session import SessionLocal
from backend.services import consent_service


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
def make_clinician(require_db: None) -> Iterator[callable]:
    del require_db
    created_ids: list[uuid.UUID] = []

    def _make(name: str) -> uuid.UUID:
        session = SessionLocal()
        person = Clinician(name=name, consent_status="granted")
        session.add(person)
        session.commit()
        created_ids.append(person.clinician_id)
        session.close()
        return created_ids[-1]

    yield _make

    cleanup = SessionLocal()
    for clinician_id in created_ids:
        cleanup.execute(delete(ConsentRegistry).where(ConsentRegistry.clinician_id == clinician_id))
        cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def a_clinician(make_clinician: callable) -> uuid.UUID:
    return make_clinician("Consent Test Clinician")


def test_institutional_clearance_blocks_by_default(require_db: None):
    del require_db
    settings = get_settings()
    original = settings.institutional_ethics_clearance_granted
    settings.institutional_ethics_clearance_granted = False
    try:
        with pytest.raises(HTTPException) as exc_info:
            consent_service.require_institutional_clearance()
        assert exc_info.value.status_code == 403
    finally:
        settings.institutional_ethics_clearance_granted = original


def test_institutional_clearance_passes_once_granted(require_db: None):
    del require_db
    settings = get_settings()
    original = settings.institutional_ethics_clearance_granted
    settings.institutional_ethics_clearance_granted = True
    try:
        consent_service.require_institutional_clearance()  # does not raise
    finally:
        settings.institutional_ethics_clearance_granted = original


def test_require_consent_rejects_when_none_recorded(a_clinician: uuid.UUID):
    session = SessionLocal()

    with pytest.raises(HTTPException) as exc_info:
        consent_service.require_consent(
            session, a_clinician, ConsentSubjectType.WALKTHROUGH_RECORDING
        )
    session.close()

    assert exc_info.value.status_code == 403


def test_require_consent_passes_once_recorded(a_clinician: uuid.UUID):
    session = SessionLocal()
    consent_service.record_consent(
        session, a_clinician, ConsentSubjectType.WALKTHROUGH_RECORDING, scope="test grant"
    )

    consent_service.require_consent(session, a_clinician, ConsentSubjectType.WALKTHROUGH_RECORDING)
    session.close()


def test_require_consent_ignores_a_revoked_grant(a_clinician: uuid.UUID):
    session = SessionLocal()
    consent = consent_service.record_consent(
        session, a_clinician, ConsentSubjectType.PATIENT_DATA_BATCH, scope="test grant"
    )
    consent.revoked_at = consent.granted_at
    session.commit()

    with pytest.raises(HTTPException):
        consent_service.require_consent(session, a_clinician, ConsentSubjectType.PATIENT_DATA_BATCH)
    session.close()


def test_a_standing_grant_does_not_satisfy_a_session_scoped_check(a_clinician: uuid.UUID):
    """reference_id=None (a standing grant) and a specific session's
    reference_id are different scopes -- one must not silently cover the
    other."""
    session = SessionLocal()
    consent_service.record_consent(
        session, a_clinician, ConsentSubjectType.PATIENT_RECORDING_SESSION, scope="standing grant"
    )

    with pytest.raises(HTTPException):
        consent_service.require_consent(
            session,
            a_clinician,
            ConsentSubjectType.PATIENT_RECORDING_SESSION,
            reference_id="session-123",
        )
    session.close()


def test_a_session_scoped_grant_satisfies_only_that_session(a_clinician: uuid.UUID):
    session = SessionLocal()
    consent_service.record_consent(
        session,
        a_clinician,
        ConsentSubjectType.PATIENT_RECORDING_SESSION,
        scope="session grant",
        reference_id="session-123",
    )

    consent_service.require_consent(
        session,
        a_clinician,
        ConsentSubjectType.PATIENT_RECORDING_SESSION,
        reference_id="session-123",
    )
    with pytest.raises(HTTPException):
        consent_service.require_consent(
            session,
            a_clinician,
            ConsentSubjectType.PATIENT_RECORDING_SESSION,
            reference_id="session-456",
        )
    session.close()


def test_consent_does_not_leak_across_clinicians(a_clinician: uuid.UUID, make_clinician: callable):
    other = make_clinician("Consent Test Clinician (other)")
    session = SessionLocal()
    consent_service.record_consent(
        session, a_clinician, ConsentSubjectType.WALKTHROUGH_RECORDING, scope="test grant"
    )

    with pytest.raises(HTTPException):
        consent_service.require_consent(session, other, ConsentSubjectType.WALKTHROUGH_RECORDING)
    session.close()
