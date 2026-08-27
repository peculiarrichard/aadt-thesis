"""Integration tests for the Layer 2 ingestion API. Requires `docker compose up
-d`; skips otherwise."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.config import get_settings
from backend.db.models import AuditLog, Clinician, IngestionQueueItem
from backend.db.session import SessionLocal
from backend.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Service-Api-Key": get_settings().ingestion_api_key}


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
        cleanup.execute(
            delete(IngestionQueueItem).where(IngestionQueueItem.clinician_id == clinician_id)
        )
        cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def clinician(make_clinician: callable) -> uuid.UUID:
    return make_clinician("Ingestion API Test Clinician")


def test_upload_creates_new_queue_item(clinician: uuid.UUID):
    response = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(clinician),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "patient reports fever for two days",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["idempotent_replay"] is False
    assert body["status"] == "received"
    assert body["redaction_summary"] == {}


def test_missing_api_key_returns_401(clinician: uuid.UUID):
    response = client.post(
        "/ingestion/transcripts",
        json={
            "clinician_id": str(clinician),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "no api key header sent",
        },
    )

    assert response.status_code == 401


def test_wrong_api_key_returns_401(clinician: uuid.UUID):
    response = client.post(
        "/ingestion/transcripts",
        headers={"X-Service-Api-Key": "not-the-right-key"},
        json={
            "clinician_id": str(clinician),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "wrong api key sent",
        },
    )

    assert response.status_code == 401


def test_consent_not_granted_returns_403(make_clinician: callable):
    unconsented = make_clinician("Unconsented Test Clinician", consent_status="pending")

    response = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(unconsented),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "should be rejected before storage",
        },
    )

    assert response.status_code == 403

    session = SessionLocal()
    rows = (
        session.execute(
            select(IngestionQueueItem).where(IngestionQueueItem.clinician_id == unconsented)
        )
        .scalars()
        .all()
    )
    session.close()
    assert rows == []


def test_upload_redacts_pii_before_storage(clinician: uuid.UUID):
    response = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(clinician),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "Contact number is 08031234567, patient otherwise stable.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["redaction_summary"] == {"PHONE": 1}

    session = SessionLocal()
    stored = session.get(IngestionQueueItem, uuid.UUID(body["ingestion_id"]))
    session.close()
    assert "08031234567" not in stored.content
    assert "[REDACTED:PHONE]" in stored.content
    assert stored.redaction_summary == {"PHONE": 1}


def test_upload_writes_audit_log_entry(clinician: uuid.UUID):
    response = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(clinician),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "audit log coverage check",
        },
    )
    ingestion_id = response.json()["ingestion_id"]

    session = SessionLocal()
    entries = (
        session.execute(
            select(AuditLog).where(
                AuditLog.clinician_id == clinician,
                AuditLog.reference_id == ingestion_id,
            )
        )
        .scalars()
        .all()
    )
    session.close()

    assert len(entries) == 1
    assert entries[0].action == "ingestion_upload"
    assert entries[0].reference_table == "ingestion_queue"


def test_retry_with_same_key_and_content_is_idempotent(clinician: uuid.UUID):
    payload = {
        "clinician_id": str(clinician),
        "idempotency_key": str(uuid.uuid4()),
        "source_type": "elicitation_session",
        "content": "patient reports fever for two days",
    }

    first = client.post("/ingestion/transcripts", headers=AUTH_HEADERS, json=payload)
    second = client.post("/ingestion/transcripts", headers=AUTH_HEADERS, json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["ingestion_id"] == second.json()["ingestion_id"]
    assert second.json()["idempotent_replay"] is True

    session = SessionLocal()
    rows = (
        session.execute(
            select(IngestionQueueItem).where(
                IngestionQueueItem.clinician_id == clinician,
                IngestionQueueItem.idempotency_key == payload["idempotency_key"],
            )
        )
        .scalars()
        .all()
    )
    session.close()
    assert len(rows) == 1


def test_retry_with_same_key_but_different_content_is_rejected(clinician: uuid.UUID):
    key = str(uuid.uuid4())
    first_payload = {
        "clinician_id": str(clinician),
        "idempotency_key": key,
        "source_type": "elicitation_session",
        "content": "original content",
    }
    second_payload = {**first_payload, "content": "different content"}

    first = client.post("/ingestion/transcripts", headers=AUTH_HEADERS, json=first_payload)
    second = client.post("/ingestion/transcripts", headers=AUTH_HEADERS, json=second_payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_different_clinicians_can_reuse_the_same_idempotency_key(make_clinician: callable):
    clinician_a = make_clinician("Ingestion API Test Clinician A")
    clinician_b = make_clinician("Ingestion API Test Clinician B")
    key = str(uuid.uuid4())
    payload_template = {
        "idempotency_key": key,
        "source_type": "elicitation_session",
        "content": "same key, different clinician",
    }

    first = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={**payload_template, "clinician_id": str(clinician_a)},
    )
    second = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={**payload_template, "clinician_id": str(clinician_b)},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["ingestion_id"] != second.json()["ingestion_id"]


def test_get_only_returns_that_clinicians_items(make_clinician: callable):
    clinician_a = make_clinician("Ingestion API Test Clinician A")
    clinician_b = make_clinician("Ingestion API Test Clinician B")

    client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(clinician_a),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "belongs to clinician A",
        },
    )
    client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(clinician_b),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "belongs to clinician B",
        },
    )

    response = client.get(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        params={"clinician_id": str(clinician_a)},
    )

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["clinician_id"] == str(clinician_a)


def test_unknown_clinician_returns_404(require_db: None):
    del require_db

    response = client.post(
        "/ingestion/transcripts",
        headers=AUTH_HEADERS,
        json={
            "clinician_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "source_type": "elicitation_session",
            "content": "orphaned upload",
        },
    )

    assert response.status_code == 404
