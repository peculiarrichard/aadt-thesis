"""Tests Phase N's minimum-case gate. Uses a low min_cases_to_build_twin
override so the test doesn't need to create 20 real cases. Requires
`docker compose up -d`; skips otherwise.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.api.google_auth import require_console_session
from backend.config import get_settings
from backend.db.enums import SourceType
from backend.db.models import Case, CasePrecedentVector, Clinician
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
def low_threshold():
    settings = get_settings()
    original = settings.min_cases_to_build_twin
    settings.min_cases_to_build_twin = 2
    yield 2
    settings.min_cases_to_build_twin = original


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
        cleanup.execute(
            delete(CasePrecedentVector).where(CasePrecedentVector.clinician_id == clinician_id)
        )
        cleanup.execute(delete(Case).where(Case.clinician_id == clinician_id))
        cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def logged_in_as():
    def _login(clinician_id: uuid.UUID) -> None:
        app.dependency_overrides[require_console_session] = lambda: clinician_id

    yield _login
    app.dependency_overrides.pop(require_console_session, None)


def _add_case(clinician_id: uuid.UUID, text: str) -> None:
    session = SessionLocal()
    session.add(
        Case(
            clinician_id=clinician_id,
            transcript_or_summary=text,
            source_type=SourceType.WALKTHROUGH,
            doctor_disposition="self_care_advice",
        )
    )
    session.commit()
    session.close()


def test_status_reports_below_threshold(
    make_clinician: callable, logged_in_as: callable, low_threshold: int
):
    clinician_id = make_clinician("Twin Build Test Clinician (below)")
    logged_in_as(clinician_id)
    _add_case(clinician_id, "case 1")

    response = client.get("/console/twin/status")

    assert response.status_code == 200
    body = response.json()
    assert body["qualifying_case_count"] == 1
    assert body["min_cases_required"] == low_threshold
    assert body["ready_to_build"] is False
    assert body["already_built"] is False


def test_build_rejects_when_below_threshold(
    make_clinician: callable, logged_in_as: callable, low_threshold: int
):
    del low_threshold
    clinician_id = make_clinician("Twin Build Test Clinician (reject)")
    logged_in_as(clinician_id)
    _add_case(clinician_id, "case 1")

    response = client.post("/console/twin/build")

    assert response.status_code == 400


def test_build_succeeds_once_threshold_met(
    make_clinician: callable, logged_in_as: callable, low_threshold: int
):
    del low_threshold
    clinician_id = make_clinician("Twin Build Test Clinician (succeed)")
    logged_in_as(clinician_id)
    _add_case(clinician_id, "fever and chills")
    _add_case(clinician_id, "headache")

    response = client.post("/console/twin/build")

    assert response.status_code == 200
    assert response.json() == {"embedded_count": 2}

    status_response = client.get("/console/twin/status")
    assert status_response.json()["already_built"] is True
