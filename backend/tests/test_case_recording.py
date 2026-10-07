"""Tests Phase M's recording/de-identified-upload/confirm-draft endpoints,
plus the privacy-scan layer wired into all of them. Whisper transcription,
the structuring agent's LLM call, and the privacy LLM review are all mocked
-- no live Ollama or real audio model needed here, and no LLM call is ever
made against the local machine running these tests. Requires
`docker compose up -d`; skips otherwise.
"""

import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.case_structuring_agent import StructuredCaseDraft
from backend.agents.pii_review_agent import PiiReviewResult
from backend.api.google_auth import require_console_session
from backend.config import get_settings
from backend.db.enums import ConsentSubjectType
from backend.db.models import AuditLog, Case, Clinician, ConsentRegistry
from backend.db.session import SessionLocal
from backend.main import app
from backend.services import consent_service

client = TestClient(app)

_SAMPLE_DRAFT = StructuredCaseDraft(
    case_text="Fever and chills, RDT positive for malaria.",
    initial_impression="Likely uncomplicated malaria.",
    questions_to_ask=["Duration of fever?"],
    examination_or_checks=None,
    factors_toward_referral=None,
    factors_against_referral="No danger signs.",
    flip_up=None,
    flip_down=None,
    red_flags=None,
    confidence=None,
    general_rule=None,
    disposition="self-care advice",
    disposition_reason="No danger signs, positive RDT.",
)

_NOT_FLAGGED = PiiReviewResult(flagged=False, details=None)


def _mock_llm_review(flagged: bool = False, details: str | None = None):
    return patch(
        "backend.services.privacy_scan.review_for_identifiability",
        return_value=PiiReviewResult(flagged=flagged, details=details),
    )


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
        cleanup.execute(delete(AuditLog).where(AuditLog.clinician_id == clinician_id))
        cleanup.execute(delete(ConsentRegistry).where(ConsentRegistry.clinician_id == clinician_id))
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
def institutional_clearance_granted():
    settings = get_settings()
    original = settings.institutional_ethics_clearance_granted
    settings.institutional_ethics_clearance_granted = True
    yield
    settings.institutional_ethics_clearance_granted = original


def test_walkthrough_recording_requires_consent(make_clinician: callable, logged_in_as: callable):
    clinician_id = make_clinician("Recording Test Clinician (no consent)")
    logged_in_as(clinician_id)

    response = client.post(
        "/console/cases/recordings",
        data={"kind": "walkthrough"},
        files={"audio": ("rec.wav", b"fake audio bytes", "audio/wav")},
    )

    assert response.status_code == 403


def test_walkthrough_recording_transcribes_structures_and_scans(
    make_clinician: callable, logged_in_as: callable
):
    """Privacy option 1: walkthrough recordings now get the same privacy
    scan as patient-related paths, even though no patient is supposed to be
    involved."""
    clinician_id = make_clinician("Recording Test Clinician (walkthrough)")
    logged_in_as(clinician_id)
    session = SessionLocal()
    consent_service.record_consent(
        session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING, scope="test"
    )
    session.close()

    with (
        patch(
            "backend.transcription.whisper_backend.transcribe_audio",
            return_value="raw transcript text",
        ),
        patch(
            "backend.api.case_recording.draft_structured_case",
            return_value=_SAMPLE_DRAFT,
        ),
        _mock_llm_review(flagged=False),
    ):
        response = client.post(
            "/console/cases/recordings",
            data={"kind": "walkthrough"},
            files={"audio": ("rec.wav", b"fake audio bytes", "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["disposition"] == "self-care advice"
    assert body["redaction_summary"] == {}
    assert body["llm_flagged"] is False


def test_walkthrough_recording_surfaces_an_llm_flag(
    make_clinician: callable, logged_in_as: callable
):
    """A real patient reference with no regex-matchable pattern (no title,
    no phone number) -- exactly what option 2 exists to catch."""
    clinician_id = make_clinician("Recording Test Clinician (walkthrough flagged)")
    logged_in_as(clinician_id)
    session = SessionLocal()
    consent_service.record_consent(
        session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING, scope="test"
    )
    session.close()

    with (
        patch(
            "backend.transcription.whisper_backend.transcribe_audio",
            return_value="My neighbor's daughter had this exact presentation last week.",
        ),
        patch(
            "backend.api.case_recording.draft_structured_case",
            return_value=_SAMPLE_DRAFT,
        ),
        _mock_llm_review(flagged=True, details="References a specific real person."),
    ):
        response = client.post(
            "/console/cases/recordings",
            data={"kind": "walkthrough"},
            files={"audio": ("rec.wav", b"fake audio bytes", "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["llm_flagged"] is True
    assert "real person" in body["llm_flag_details"]


def test_patient_recording_requires_institutional_clearance(
    make_clinician: callable, logged_in_as: callable
):
    clinician_id = make_clinician("Recording Test Clinician (patient, no clearance)")
    logged_in_as(clinician_id)

    response = client.post(
        "/console/cases/recordings",
        data={"kind": "patient_consultation", "session_reference_id": "session-1"},
        files={"audio": ("rec.wav", b"fake audio bytes", "audio/wav")},
    )

    assert response.status_code == 403


def test_patient_recording_deidentifies_before_structuring(
    make_clinician: callable, logged_in_as: callable, institutional_clearance_granted: None
):
    del institutional_clearance_granted
    clinician_id = make_clinician("Recording Test Clinician (patient)")
    logged_in_as(clinician_id)
    session = SessionLocal()
    consent_service.record_consent(
        session,
        clinician_id,
        ConsentSubjectType.PATIENT_RECORDING_SESSION,
        scope="test",
        reference_id="session-1",
    )
    session.close()

    with (
        patch(
            "backend.transcription.whisper_backend.transcribe_audio",
            return_value="Patient is Mr. John Smith, fever and chills.",
        ),
        patch(
            "backend.api.case_recording.draft_structured_case",
            return_value=_SAMPLE_DRAFT,
        ) as mocked_structure,
        _mock_llm_review(flagged=False),
    ):
        response = client.post(
            "/console/cases/recordings",
            data={"kind": "patient_consultation", "session_reference_id": "session-1"},
            files={"audio": ("rec.wav", b"fake audio bytes", "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["redaction_summary"]  # at least one redaction (the name)
    structured_arg = mocked_structure.call_args[0][0]
    assert "John Smith" not in structured_arg


def test_deidentified_text_upload_requires_both_gates(
    make_clinician: callable, logged_in_as: callable
):
    clinician_id = make_clinician("Upload Test Clinician (no gates)")
    logged_in_as(clinician_id)

    response = client.post(
        "/console/cases/from-deidentified-text", json={"text": "a de-identified case summary"}
    )

    assert response.status_code == 403


def test_deidentified_text_upload_succeeds_with_both_gates(
    make_clinician: callable, logged_in_as: callable, institutional_clearance_granted: None
):
    del institutional_clearance_granted
    clinician_id = make_clinician("Upload Test Clinician")
    logged_in_as(clinician_id)
    session = SessionLocal()
    consent_service.record_consent(
        session, clinician_id, ConsentSubjectType.PATIENT_DATA_BATCH, scope="test"
    )
    session.close()

    with (
        patch("backend.api.case_recording.draft_structured_case", return_value=_SAMPLE_DRAFT),
        _mock_llm_review(flagged=False),
    ):
        response = client.post(
            "/console/cases/from-deidentified-text",
            json={"text": "a de-identified case summary"},
        )

    assert response.status_code == 200
    assert response.json()["disposition"] == "self-care advice"


def test_confirm_draft_rejects_without_attestation(
    make_clinician: callable, logged_in_as: callable
):
    """Privacy option 3: the per-case attestation is required on every save,
    unconditionally -- not just when something was flagged."""
    clinician_id = make_clinician("Confirm Draft Test Clinician (no attestation)")
    logged_in_as(clinician_id)

    with _mock_llm_review(flagged=False):
        response = client.post(
            "/console/cases/confirm-draft",
            json={
                "case_text": "Fever and chills.",
                "disposition": "self-care advice",
                "source_type": "walkthrough",
                "attestation_confirmed": False,
            },
        )

    assert response.status_code == 400


def test_confirm_draft_creates_a_case_with_attestation(
    make_clinician: callable, logged_in_as: callable
):
    clinician_id = make_clinician("Confirm Draft Test Clinician")
    logged_in_as(clinician_id)

    with _mock_llm_review(flagged=False):
        response = client.post(
            "/console/cases/confirm-draft",
            json={
                "case_text": "Fever and chills.",
                "disposition": "self-care advice",
                "source_type": "walkthrough",
                "attestation_confirmed": True,
            },
        )

    assert response.status_code == 200
    case_id = response.json()["case_id"]

    session = SessionLocal()
    case = session.get(Case, uuid.UUID(case_id))
    audit_entries = (
        session.execute(select(AuditLog).where(AuditLog.reference_id == case_id)).scalars().all()
    )
    session.close()
    assert case is not None
    assert case.doctor_disposition == "self_care_advice"
    assert case.source_type.value == "walkthrough"
    assert len(audit_entries) == 1
    assert audit_entries[0].action == "case_saved"


def test_confirm_draft_redacts_regardless_of_attestation(
    make_clinician: callable, logged_in_as: callable
):
    """The regex-redaction floor (option 1) applies even when the doctor has
    attested the case is clean -- her attestation covers what the LLM flag
    advises on, not a bypass of the hard pattern-matched floor."""
    clinician_id = make_clinician("Confirm Draft Test Clinician (redaction floor)")
    logged_in_as(clinician_id)

    with _mock_llm_review(flagged=False):
        response = client.post(
            "/console/cases/confirm-draft",
            json={
                "case_text": "Contact Mr. John Doe on 08012345678.",
                "disposition": "self-care advice",
                "source_type": "walkthrough",
                "attestation_confirmed": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["redaction_summary"]  # NAME and/or PHONE caught

    session = SessionLocal()
    case = session.get(Case, uuid.UUID(body["case_id"]))
    session.close()
    assert "John Doe" not in case.transcript_or_summary
    assert "08012345678" not in case.transcript_or_summary


def test_confirm_draft_audit_logs_a_flagged_save_differently(
    make_clinician: callable, logged_in_as: callable
):
    clinician_id = make_clinician("Confirm Draft Test Clinician (flagged)")
    logged_in_as(clinician_id)

    with _mock_llm_review(flagged=True, details="References a specific real person."):
        response = client.post(
            "/console/cases/confirm-draft",
            json={
                "case_text": "My neighbor's son had this.",
                "disposition": "self-care advice",
                "source_type": "walkthrough",
                "attestation_confirmed": True,
            },
        )

    assert response.status_code == 200
    case_id = response.json()["case_id"]

    session = SessionLocal()
    audit_entries = (
        session.execute(select(AuditLog).where(AuditLog.reference_id == case_id)).scalars().all()
    )
    session.close()
    assert audit_entries[0].action == "case_saved_with_privacy_flag"
