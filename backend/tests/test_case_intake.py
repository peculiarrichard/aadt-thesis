"""Tests Phase K's self-service walkthrough-case intake: bulk JSON/xlsx upload
and the one-by-one form, all gated by WALKTHROUGH_RECORDING consent (no
institutional clearance needed -- no patient involved), and all going through
the scan-then-review-then-confirm flow (privacy option 4) rather than saving
directly. The LLM privacy review is mocked throughout -- no real Ollama call.
Requires `docker compose up -d`; skips otherwise.
"""

import io
import json
import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.pii_review_agent import PiiReviewResult
from backend.api.google_auth import require_console_session
from backend.db.enums import ConsentSubjectType
from backend.db.models import AuditLog, Case, Clinician, ConsentRegistry
from backend.db.session import SessionLocal
from backend.main import app
from backend.services import consent_service

client = TestClient(app)


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
def consenting_clinician(make_clinician: callable, logged_in_as: callable) -> uuid.UUID:
    clinician_id = make_clinician("Case Intake Test Clinician")
    session = SessionLocal()
    consent_service.record_consent(
        session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING, scope="test"
    )
    session.close()
    logged_in_as(clinician_id)
    return clinician_id


_VALID_RECORD = {
    "case_id": "T-001",
    "case_text": "Fever and chills, RDT positive for malaria.",
    "disposition": "self-care advice",
    "disposition_reason": "Uncomplicated case, no danger signs.",
    "questions_to_ask": ["Duration of fever?", "Any danger signs?"],
}


def test_form_scan_requires_consent(make_clinician: callable, logged_in_as: callable):
    clinician_id = make_clinician("Case Intake Test Clinician (no consent)")
    logged_in_as(clinician_id)

    response = client.post("/console/cases/scan", json=_VALID_RECORD)

    assert response.status_code == 403


def test_form_scan_returns_a_draft_without_saving(consenting_clinician: uuid.UUID):
    with _mock_llm_review(flagged=False):
        response = client.post("/console/cases/scan", json=_VALID_RECORD)

    assert response.status_code == 200
    body = response.json()
    assert body["disposition"] == "self-care advice"
    assert body["case_text"] == _VALID_RECORD["case_text"]
    assert body["redaction_summary"] == {}
    assert body["llm_flagged"] is False

    session = SessionLocal()
    count = len(
        session.execute(select(Case).where(Case.clinician_id == consenting_clinician))
        .scalars()
        .all()
    )
    session.close()
    assert count == 0  # scan never saves


def test_form_scan_rejects_an_unknown_disposition(consenting_clinician: uuid.UUID):
    bad_record = {**_VALID_RECORD, "disposition": "not a real disposition"}

    with _mock_llm_review(flagged=False):
        response = client.post("/console/cases/scan", json=bad_record)

    assert response.status_code == 400


def test_form_scan_redacts_pattern_matched_pii(consenting_clinician: uuid.UUID):
    record = {**_VALID_RECORD, "case_text": "Discussed with Dr. Jane Okafor, agreed to monitor."}

    with _mock_llm_review(flagged=False):
        response = client.post("/console/cases/scan", json=record)

    body = response.json()
    assert "[REDACTED:NAME]" in body["case_text"]
    assert body["redaction_summary"] == {"NAME": 1}


def test_scan_then_confirm_creates_exactly_one_case(consenting_clinician: uuid.UUID):
    with _mock_llm_review(flagged=False):
        scan_response = client.post("/console/cases/scan", json=_VALID_RECORD)
    draft = scan_response.json()

    with _mock_llm_review(flagged=False):
        confirm_response = client.post(
            "/console/cases/confirm-draft",
            json={**draft, "source_type": "walkthrough", "attestation_confirmed": True},
        )

    assert confirm_response.status_code == 200
    session = SessionLocal()
    case = session.execute(
        select(Case).where(Case.clinician_id == consenting_clinician)
    ).scalar_one()
    session.close()
    assert case.doctor_disposition == "self_care_advice"
    assert case.external_case_ref == "T-001"


def test_bulk_json_upload_returns_drafts_without_saving(consenting_clinician: uuid.UUID):
    payload = {
        "cases": [
            _VALID_RECORD,
            {**_VALID_RECORD, "case_id": "T-002", "disposition": "urgent referral"},
        ]
    }
    files = {"file": ("cases.json", json.dumps(payload).encode(), "application/json")}

    with _mock_llm_review(flagged=False):
        response = client.post("/console/cases/bulk-upload", files=files)

    assert response.status_code == 200
    drafts = response.json()["drafts"]
    assert len(drafts) == 2
    assert {d["case_id"] for d in drafts} == {"T-001", "T-002"}

    session = SessionLocal()
    count = len(
        session.execute(select(Case).where(Case.clinician_id == consenting_clinician))
        .scalars()
        .all()
    )
    session.close()
    assert count == 0  # bulk scan never saves either


def test_bulk_xlsx_upload_returns_a_draft_with_parsed_fields(consenting_clinician: uuid.UUID):
    from backend.services.case_upload_parsing import FIELD_COLUMNS

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(FIELD_COLUMNS))
    sheet.append(
        [
            "T-003",
            "Headache, thunderclap onset.",
            None,
            "Worst headache of life?|Neck stiffness?",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "urgent referral",
            "Red flag presentation.",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    files = {
        "file": (
            "cases.xlsx",
            buffer.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    with _mock_llm_review(flagged=False):
        response = client.post("/console/cases/bulk-upload", files=files)

    assert response.status_code == 200
    drafts = response.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["questions_to_ask"] == ["Worst headache of life?", "Neck stiffness?"]
    assert drafts[0]["disposition"] == "urgent referral"


def test_json_template_downloads(require_db: None):
    del require_db
    response = client.get("/console/cases/template")

    assert response.status_code == 200
    body = response.json()
    assert "cases" in body


def test_xlsx_template_downloads(require_db: None):
    del require_db
    response = client.get("/console/cases/template.xlsx")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
