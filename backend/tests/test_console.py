"""Integration tests for the console API (Layer 8, Section 5.8). Requires
`docker compose up -d`; skips otherwise. Overrides require_console_session
rather than going through a real Google login -- that flow is covered
separately in test_google_auth.py.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.api.google_auth import require_console_session
from backend.db.enums import GraphNodeType, SourceType
from backend.db.models import AuditLog, Case, Clinician, GuidelineDocument, GuidelineGraphNode
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
def make_clinician(require_db: None) -> Iterator[callable]:
    del require_db
    created_ids: list[uuid.UUID] = []

    def _make(name: str, consent_status: str = "granted") -> uuid.UUID:
        session = SessionLocal()
        person = Clinician(name=name, consent_status=consent_status)
        session.add(person)
        session.commit()
        created_ids.append(person.clinician_id)
        session.close()
        return created_ids[-1]

    yield _make

    cleanup = SessionLocal()
    for clinician_id in created_ids:
        cleanup.execute(delete(AuditLog).where(AuditLog.clinician_id == clinician_id))
        cleanup.execute(delete(Case).where(Case.clinician_id == clinician_id))
        cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def guideline_fixture(require_db: None) -> Iterator[None]:
    del require_db
    session = SessionLocal()
    document = GuidelineDocument(title="Console Test Fixture", source="test-fixture")
    session.add(document)
    session.flush()
    session.add(
        GuidelineGraphNode(
            document_id=document.document_id, node_type=GraphNodeType.CONDITION, label="MALARIA"
        )
    )
    session.commit()
    document_id = document.document_id
    session.close()

    yield

    cleanup = SessionLocal()
    cleanup.execute(delete(GuidelineGraphNode).where(GuidelineGraphNode.document_id == document_id))
    cleanup.execute(delete(GuidelineDocument).where(GuidelineDocument.document_id == document_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def logged_in_as():
    def _login(clinician_id: uuid.UUID) -> None:
        app.dependency_overrides[require_console_session] = lambda: clinician_id

    yield _login
    app.dependency_overrides.pop(require_console_session, None)


def test_cases_requires_a_session(make_clinician: callable):
    del make_clinician
    response = client.get("/console/cases")
    assert response.status_code == 401


def test_cases_returns_only_the_logged_in_clinicians_cases(
    make_clinician: callable, logged_in_as: callable
):
    owner = make_clinician("Console Test Clinician (owner)")
    other = make_clinician("Console Test Clinician (other)")
    session = SessionLocal()
    session.add(
        Case(
            clinician_id=owner,
            transcript_or_summary="belongs to owner",
            source_type=SourceType.ELICITATION_SESSION,
        )
    )
    session.add(
        Case(
            clinician_id=other,
            transcript_or_summary="belongs to other",
            source_type=SourceType.ELICITATION_SESSION,
        )
    )
    session.commit()
    session.close()

    logged_in_as(owner)
    response = client.get("/console/cases")

    assert response.status_code == 200
    bodies = response.json()
    assert len(bodies) == 1
    assert bodies[0]["presenting_summary"] == "belongs to owner"


def test_case_result_404s_for_another_clinicians_case(
    make_clinician: callable, logged_in_as: callable
):
    owner = make_clinician("Console Test Clinician (result owner)")
    stranger = make_clinician("Console Test Clinician (result stranger)")
    session = SessionLocal()
    case = Case(
        clinician_id=owner,
        transcript_or_summary="belongs to owner",
        source_type=SourceType.ELICITATION_SESSION,
    )
    session.add(case)
    session.commit()
    case_id = case.case_id
    session.close()

    logged_in_as(stranger)
    response = client.get(f"/console/cases/{case_id}/result")

    assert response.status_code == 404


def test_case_result_rejects_an_unknown_config(make_clinician: callable, logged_in_as: callable):
    owner = make_clinician("Console Test Clinician (bad config)")
    session = SessionLocal()
    case = Case(
        clinician_id=owner,
        transcript_or_summary="fever",
        source_type=SourceType.ELICITATION_SESSION,
    )
    session.add(case)
    session.commit()
    case_id = case.case_id
    session.close()

    logged_in_as(owner)
    response = client.get(f"/console/cases/{case_id}/result", params={"config": "not_a_config"})

    assert response.status_code == 400


def test_case_result_runs_the_default_deterministic_config(
    make_clinician: callable, logged_in_as: callable, guideline_fixture: None
):
    """Default config (guideline_plus_precedent) makes no LLM call, so this
    stays fast and doesn't need a live Ollama."""
    del guideline_fixture
    owner = make_clinician("Console Test Clinician (live result)")
    session = SessionLocal()
    case = Case(
        clinician_id=owner,
        transcript_or_summary="fever and chills, RDT positive for malaria, no danger signs",
        source_type=SourceType.ELICITATION_SESSION,
    )
    session.add(case)
    session.commit()
    case_id = case.case_id
    session.close()

    logged_in_as(owner)
    response = client.get(f"/console/cases/{case_id}/result")

    assert response.status_code == 200
    body = response.json()
    assert body["config_label"] == "guideline_plus_precedent"
    assert "MALARIA" in body["explanation"]["matched_conditions"]
