"""Integration tests for the Layer 6 service layer (task 10): two dummy tenants,
one consented and one not. Requires `docker compose up -d`; skips otherwise."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.db.enums import GraphNodeType, SourceType
from backend.db.models import (
    AuditLog,
    Clinician,
    Consultation,
    GuidelineDocument,
    GuidelineGraphNode,
)
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass
from backend.services import ai_ml_service, cognitive_services, data_services, xai_service
from backend.services.connector import Connector, ConnectorError, ConnectorPolicyError


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

    def _make(name: str, consent_status: str) -> uuid.UUID:
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
        cleanup.execute(delete(Consultation).where(Consultation.clinician_id == clinician_id))
        cleanup.execute(delete(Clinician).where(Clinician.clinician_id == clinician_id))
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def consented_clinician(make_clinician: callable) -> uuid.UUID:
    return make_clinician("Services Test Clinician (consented)", "granted")


@pytest.fixture
def unconsented_clinician(make_clinician: callable) -> uuid.UUID:
    return make_clinician("Services Test Clinician (unconsented)", "pending")


@pytest.fixture
def guideline_fixture(require_db: None) -> Iterator[None]:
    """One real condition label so reason()/run_consultation have evidence to find."""
    del require_db
    session = SessionLocal()
    document = GuidelineDocument(title="Services Test Fixture", source="test-fixture")
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


# --- Connector -----------------------------------------------------------------


def test_connector_raises_for_unknown_clinician(require_db: None):
    del require_db
    session = SessionLocal()
    connector = Connector(session, uuid.uuid4())

    with pytest.raises(ConnectorError):
        connector.authorize()
    session.close()


def test_connector_raises_for_unconsented_clinician(unconsented_clinician: uuid.UUID):
    session = SessionLocal()
    connector = Connector(session, unconsented_clinician)

    with pytest.raises(ConnectorPolicyError):
        connector.authorize()
    session.close()


def test_connector_record_writes_audit_log(consented_clinician: uuid.UUID):
    session = SessionLocal()
    connector = Connector(session, consented_clinician)
    connector.authorize()
    connector.record(
        "test_action", reference_table="clinicians", reference_id=str(consented_clinician)
    )
    session.commit()

    entries = (
        session.execute(select(AuditLog).where(AuditLog.clinician_id == consented_clinician))
        .scalars()
        .all()
    )
    session.close()

    assert len(entries) == 1
    assert entries[0].action == "connector:AHDT->DDT:test_action"


# --- Data services ---------------------------------------------------------------


def test_data_services_scoped_to_consented_clinician(consented_clinician: uuid.UUID):
    session = SessionLocal()
    data_services.create_consultation(
        session,
        consented_clinician,
        patient_ref="synthetic-ref",
        transcript_or_summary="scoping test",
        source_type=SourceType.ELICITATION_SESSION,
    )
    session.commit()

    results = data_services.list_consultations(session, consented_clinician)
    session.close()

    assert len(results) == 1
    assert results[0].clinician_id == consented_clinician


def test_data_services_reject_unconsented_clinician(unconsented_clinician: uuid.UUID):
    session = SessionLocal()

    with pytest.raises(ConnectorPolicyError):
        data_services.list_consultations(session, unconsented_clinician)
    session.close()


def test_data_services_do_not_leak_across_clinicians(
    consented_clinician: uuid.UUID, make_clinician: callable
):
    other = make_clinician("Services Test Clinician (other)", "granted")
    session = SessionLocal()
    data_services.create_consultation(
        session,
        consented_clinician,
        patient_ref="a",
        transcript_or_summary="belongs to consented_clinician",
        source_type=SourceType.ELICITATION_SESSION,
    )
    data_services.create_consultation(
        session,
        other,
        patient_ref="b",
        transcript_or_summary="belongs to other",
        source_type=SourceType.ELICITATION_SESSION,
    )
    session.commit()

    results = data_services.list_consultations(session, consented_clinician)
    session.close()

    assert len(results) == 1
    assert results[0].transcript_or_summary == "belongs to consented_clinician"


# --- AI/ML, XAI, and cognitive services --------------------------------------


def test_ai_ml_service_proposes_a_disposition(
    consented_clinician: uuid.UUID, guideline_fixture: None
):
    del guideline_fixture
    session = SessionLocal()
    output = ai_ml_service.propose_disposition(
        session,
        consented_clinician,
        presenting_complaint="fever and chills",
        history="RDT positive for malaria",
        examination_findings="no danger signs",
    )
    session.close()

    assert output.disposition == DispositionClass.MANAGE_AT_PRIMARY_CARE
    assert not output.escalated


def test_ai_ml_service_rejects_unconsented_clinician(unconsented_clinician: uuid.UUID):
    session = SessionLocal()

    with pytest.raises(ConnectorPolicyError):
        ai_ml_service.propose_disposition(
            session, unconsented_clinician, "fever", "history", "findings"
        )
    session.close()


def test_xai_service_returns_the_agent_explanation(
    consented_clinician: uuid.UUID, guideline_fixture: None
):
    del guideline_fixture
    session = SessionLocal()
    output = ai_ml_service.propose_disposition(
        session,
        consented_clinician,
        "fever and chills",
        "RDT positive for malaria",
        "no danger signs",
    )
    explanation = xai_service.get_explanation(session, consented_clinician, output)
    session.close()

    assert explanation is output.explanation
    assert "MALARIA" in explanation.matched_conditions


def test_run_consultation_returns_disposition_when_not_escalated(
    consented_clinician: uuid.UUID, guideline_fixture: None
):
    del guideline_fixture
    session = SessionLocal()
    result = cognitive_services.run_consultation(
        session,
        consented_clinician,
        "fever and chills",
        "RDT positive for malaria",
        "no danger signs",
    )
    session.close()

    assert result.escalated is False
    assert result.disposition == DispositionClass.MANAGE_AT_PRIMARY_CARE


def test_run_consultation_withholds_disposition_when_escalated(consented_clinician: uuid.UUID):
    session = SessionLocal()
    result = cognitive_services.run_consultation(
        session,
        consented_clinician,
        "crushing central chest pain",
        "known hypertensive",
        "ECG shows ST-segment elevation",
    )
    session.close()

    assert result.escalated is True
    assert result.disposition is None


def test_run_consultation_rejects_unconsented_clinician(unconsented_clinician: uuid.UUID):
    session = SessionLocal()

    with pytest.raises(ConnectorPolicyError):
        cognitive_services.run_consultation(
            session, unconsented_clinician, "fever", "history", "findings"
        )
    session.close()


def test_run_consultation_writes_a_connector_audit_trail(
    consented_clinician: uuid.UUID, guideline_fixture: None
):
    del guideline_fixture
    session = SessionLocal()
    cognitive_services.run_consultation(
        session,
        consented_clinician,
        "fever and chills",
        "RDT positive for malaria",
        "no danger signs",
    )
    session.commit()

    actions = {
        row.action
        for row in session.execute(
            select(AuditLog).where(AuditLog.clinician_id == consented_clinician)
        ).scalars()
    }
    session.close()

    assert "connector:AHDT->DDT:cognitive_perceive" in actions
    assert "connector:AHDT->DDT:cognitive_reason" in actions
    assert "connector:AHDT->DDT:cognitive_act" in actions
    assert "connector:AHDT->DDT:xai_explain" in actions
