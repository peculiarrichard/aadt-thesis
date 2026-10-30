"""Patient-facing chat intake + human-in-the-loop review (Phase W/X,
simulated patients only) -- mirrors test_consult.py's shape: the LLM calls
inside patient_intake_agent and twin_agent are mocked; BGE-M3 embedding calls
are real, same as the rest of this project's DB-backed tests. Requires
`docker compose up -d` with the patient-facing migration applied; skips
otherwise.
"""

import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.patient_intake_agent import IntakeTurn
from backend.agents.persona_agent import PersonaDraft
from backend.api.google_auth import require_console_session
from backend.db.enums import PatientChatStatus, SourceType
from backend.db.models import (
    Case,
    CasePrecedentVector,
    Clinician,
    InteractionLog,
    Patient,
    PatientChatMessage,
    PatientChatSession,
    Review,
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
def built_twin_clinician(require_db: None) -> Iterator[uuid.UUID]:
    del require_db
    session = SessionLocal()
    clinician = Clinician(name="Patient Chat Test Clinician", consent_status="granted")
    session.add(clinician)
    session.flush()
    case = Case(
        clinician_id=clinician.clinician_id,
        transcript_or_summary="an existing precedent case",
        source_type=SourceType.WALKTHROUGH,
        doctor_disposition="self_care_advice",
    )
    session.add(case)
    session.flush()
    session.add(
        CasePrecedentVector(
            clinician_id=clinician.clinician_id, case_id=case.case_id, embedding=[0.0] * 1024
        )
    )
    session.commit()
    clinician_id = clinician.clinician_id
    session.close()

    yield clinician_id

    cleanup = SessionLocal()
    cleanup.execute(
        delete(Review).where(
            Review.patient_chat_session_id.in_(
                select(PatientChatSession.session_id).where(
                    PatientChatSession.clinician_id == clinician_id
                )
            )
        )
    )
    cleanup.execute(
        delete(PatientChatMessage).where(
            PatientChatMessage.session_id.in_(
                select(PatientChatSession.session_id).where(
                    PatientChatSession.clinician_id == clinician_id
                )
            )
        )
    )
    cleanup.execute(
        delete(PatientChatSession).where(PatientChatSession.clinician_id == clinician_id)
    )
    cleanup.execute(delete(InteractionLog).where(InteractionLog.clinician_id == clinician_id))
    cleanup.execute(
        delete(CasePrecedentVector).where(CasePrecedentVector.clinician_id == clinician_id)
    )
    cleanup.execute(delete(Case).where(Case.clinician_id == clinician_id))
    cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def patient_id(require_db: None) -> Iterator[uuid.UUID]:
    del require_db
    email = f"patient-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/patient/signup",
        json={"email": email, "password": "sim-pw", "username": f"sim-{uuid.uuid4().hex[:6]}"},
    )
    assert response.status_code == 200
    pid = uuid.UUID(response.json()["patient_id"])

    yield pid

    cleanup = SessionLocal()
    cleanup.execute(delete(Patient).where(Patient.patient_id == pid))
    cleanup.commit()
    cleanup.close()


def _as_clinician(clinician_id: uuid.UUID) -> None:
    app.dependency_overrides[require_console_session] = lambda: clinician_id


def _clear_clinician_override() -> None:
    app.dependency_overrides.pop(require_console_session, None)


def test_chat_session_runs_the_twin_and_lands_in_pending_review(
    built_twin_clinician: uuid.UUID, patient_id: uuid.UUID
):
    del patient_id  # signup already established the session cookie on `client`
    create_response = client.post(
        "/patient/chat/sessions",
        json={
            "clinician_id": str(built_twin_clinician),
            "presenting_complaint": "fever and chills",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    with (
        patch(
            "backend.api.patient_chat.next_intake_turn",
            return_value=IntakeTurn(question=None, case_summary="3 days of fever and chills"),
        ),
        patch(
            "backend.agents.twin_agent.draft_from_persona",
            return_value=PersonaDraft(
                disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="matches precedent"
            ),
        ),
        client.websocket_connect(f"/patient/chat/ws/{session_id}") as websocket,
    ):
        message = websocket.receive_json()

    assert message == {"type": "submitted_for_review"}

    status_response = client.get(f"/patient/chat/sessions/{session_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["pending"] is True
    assert body["status"] == PatientChatStatus.PENDING_DOCTOR_REVIEW.value
    assert "self care advice" in body["report"]["assessment"]


def test_doctor_approves_a_pending_chat(built_twin_clinician: uuid.UUID, patient_id: uuid.UUID):
    del patient_id
    create_response = client.post(
        "/patient/chat/sessions",
        json={"clinician_id": str(built_twin_clinician), "presenting_complaint": "sore throat"},
    )
    session_id = create_response.json()["session_id"]

    with (
        patch(
            "backend.api.patient_chat.next_intake_turn",
            return_value=IntakeTurn(question=None, case_summary="sore throat, no fever"),
        ),
        patch(
            "backend.agents.twin_agent.draft_from_persona",
            return_value=PersonaDraft(
                disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="matches precedent"
            ),
        ),
        client.websocket_connect(f"/patient/chat/ws/{session_id}"),
    ):
        pass

    _as_clinician(built_twin_clinician)
    try:
        pending_response = client.get("/console/patient-chats")
        assert pending_response.status_code == 200
        assert any(c["session_id"] == session_id for c in pending_response.json())

        review_response = client.post(
            f"/console/patient-chats/{session_id}/review", json={"action": "approved"}
        )
        assert review_response.status_code == 200
        assert review_response.json()["new_case_id"] is None
    finally:
        _clear_clinician_override()

    final_response = client.get(f"/patient/chat/sessions/{session_id}")
    assert final_response.json()["pending"] is False


def test_doctor_correction_creates_a_case_and_folds_into_precedent_memory(
    built_twin_clinician: uuid.UUID, patient_id: uuid.UUID
):
    del patient_id
    create_response = client.post(
        "/patient/chat/sessions",
        json={
            "clinician_id": str(built_twin_clinician),
            "presenting_complaint": "thunderclap headache",
        },
    )
    session_id = create_response.json()["session_id"]

    with (
        patch(
            "backend.api.patient_chat.next_intake_turn",
            return_value=IntakeTurn(question=None, case_summary="thunderclap headache, worst ever"),
        ),
        patch(
            "backend.agents.twin_agent.draft_from_persona",
            return_value=PersonaDraft(
                disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="initial draft"
            ),
        ),
        client.websocket_connect(f"/patient/chat/ws/{session_id}"),
    ):
        pass

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

    _as_clinician(built_twin_clinician)
    try:
        review_response = client.post(
            f"/console/patient-chats/{session_id}/review",
            json={
                "action": "corrected",
                "corrected_disposition": "urgent referral",
                "corrected_reasoning": "red flag presentation, should have escalated",
            },
        )
    finally:
        _clear_clinician_override()

    assert review_response.status_code == 200
    new_case_id = review_response.json()["new_case_id"]
    assert new_case_id is not None

    session = SessionLocal()
    new_case = session.get(Case, uuid.UUID(new_case_id))
    assert new_case.source_type == SourceType.PATIENT_CHAT_FEEDBACK
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
