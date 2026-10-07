"""Tests Phase O's ad-hoc consult and feedback loop -- in particular that a
CORRECTED verdict creates exactly one new Case row and folds it into
precedent memory so a later retrieval can find it. The LLM call inside
run_twin_agent is mocked (FULL_SYSTEM uses persona conditioning); BGE-M3
embedding calls are real, same as the rest of this project's DB-backed tests.
Requires `docker compose up -d` and a real guideline fixture; skips otherwise.
"""

import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.persona_agent import PersonaDraft
from backend.api.google_auth import require_console_session
from backend.db.enums import SourceType
from backend.db.models import (
    Case,
    CasePrecedentVector,
    Clinician,
    InteractionLog,
)
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass
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
        cleanup.execute(delete(InteractionLog).where(InteractionLog.clinician_id == clinician_id))
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


@pytest.fixture
def built_twin_clinician(make_clinician: callable, logged_in_as: callable) -> uuid.UUID:
    """A clinician with one existing case already embedded -- has_precedent_memory
    is true, satisfying the consult gate."""
    clinician_id = make_clinician("Consult Test Clinician")
    session = SessionLocal()
    case = Case(
        clinician_id=clinician_id,
        transcript_or_summary="an existing precedent case",
        source_type=SourceType.WALKTHROUGH,
        doctor_disposition="self_care_advice",
    )
    session.add(case)
    session.flush()
    session.add(
        CasePrecedentVector(clinician_id=clinician_id, case_id=case.case_id, embedding=[0.0] * 1024)
    )
    session.commit()
    session.close()
    logged_in_as(clinician_id)
    return clinician_id


def test_consult_rejects_when_twin_not_built(make_clinician: callable, logged_in_as: callable):
    clinician_id = make_clinician("Consult Test Clinician (no twin)")
    logged_in_as(clinician_id)

    response = client.post("/console/consult", json={"case_text": "fever and chills"})

    assert response.status_code == 400


def test_consult_runs_the_full_twin(built_twin_clinician: uuid.UUID):
    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="matches precedent"
        ),
    ):
        response = client.post("/console/consult", json={"case_text": "fever and chills"})

    assert response.status_code == 200
    body = response.json()
    assert body["config_label"] == "full_system"
    assert "interaction_id" in body


def test_corrected_feedback_creates_a_case_and_folds_into_precedent_memory(
    built_twin_clinician: uuid.UUID,
):
    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="initial draft"
        ),
    ):
        consult_response = client.post(
            "/console/consult", json={"case_text": "thunderclap headache"}
        )
    interaction_id = consult_response.json()["interaction_id"]

    before_count = (
        SessionLocal()
        .execute(
            select(CasePrecedentVector).where(
                CasePrecedentVector.clinician_id == built_twin_clinician
            )
        )
        .scalars()
        .all()
    )

    feedback_response = client.post(
        f"/console/consult/{interaction_id}/feedback",
        json={
            "action": "corrected",
            "case_text": "thunderclap headache",
            "corrected_disposition": "urgent referral",
            "corrected_reasoning": "red flag presentation, should have escalated",
        },
    )

    assert feedback_response.status_code == 200
    body = feedback_response.json()
    assert body["logged"] is True
    assert body["new_case_id"] is not None

    session = SessionLocal()
    new_case = session.get(Case, uuid.UUID(body["new_case_id"]))
    assert new_case.source_type == SourceType.CONSULT_FEEDBACK
    assert new_case.doctor_disposition == "urgent_referral"

    after_count = (
        session.execute(
            select(CasePrecedentVector).where(
                CasePrecedentVector.clinician_id == built_twin_clinician
            )
        )
        .scalars()
        .all()
    )
    session.close()

    assert len(after_count) == len(before_count) + 1


def test_approved_feedback_does_not_create_a_case(built_twin_clinician: uuid.UUID):
    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="initial draft"
        ),
    ):
        consult_response = client.post("/console/consult", json={"case_text": "mild cough"})
    interaction_id = consult_response.json()["interaction_id"]

    response = client.post(
        f"/console/consult/{interaction_id}/feedback",
        json={"action": "approved", "case_text": "mild cough"},
    )

    assert response.status_code == 200
    assert response.json()["new_case_id"] is None


def test_feedback_404s_for_another_clinicians_interaction(
    built_twin_clinician: uuid.UUID, make_clinician: callable
):
    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="initial draft"
        ),
    ):
        consult_response = client.post("/console/consult", json={"case_text": "sore throat"})
    interaction_id = consult_response.json()["interaction_id"]

    stranger = make_clinician("Consult Test Clinician (stranger)")
    app.dependency_overrides[require_console_session] = lambda: stranger

    response = client.post(
        f"/console/consult/{interaction_id}/feedback",
        json={"action": "approved", "case_text": "sore throat"},
    )

    assert response.status_code == 404
