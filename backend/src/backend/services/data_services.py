"""Layer 6.2 data services (Section 5.6.2): consultations/interaction_log, scoped
by clinician_id + consent (reuses Connector's policy check)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.enums import ClinicianAction, Mode, SourceType
from backend.db.models import Consultation, InteractionLog
from backend.services.connector import Connector


def _require_consent(session: Session, clinician_id: uuid.UUID) -> None:
    Connector(session, clinician_id).authorize()


def list_consultations(session: Session, clinician_id: uuid.UUID) -> list[Consultation]:
    _require_consent(session, clinician_id)
    return (
        session.execute(select(Consultation).where(Consultation.clinician_id == clinician_id))
        .scalars()
        .all()
    )


def create_consultation(
    session: Session,
    clinician_id: uuid.UUID,
    patient_ref: str,
    transcript_or_summary: str,
    source_type: SourceType,
    doctor_disposition: str | None = None,
    doctor_reasoning_notes: str | None = None,
) -> Consultation:
    _require_consent(session, clinician_id)
    consultation = Consultation(
        clinician_id=clinician_id,
        patient_ref=patient_ref,
        transcript_or_summary=transcript_or_summary,
        source_type=source_type,
        doctor_disposition=doctor_disposition,
        doctor_reasoning_notes=doctor_reasoning_notes,
    )
    session.add(consultation)
    session.flush()
    return consultation


def list_interaction_log(session: Session, clinician_id: uuid.UUID) -> list[InteractionLog]:
    _require_consent(session, clinician_id)
    return (
        session.execute(select(InteractionLog).where(InteractionLog.clinician_id == clinician_id))
        .scalars()
        .all()
    )


def create_interaction_log_entry(
    session: Session,
    clinician_id: uuid.UUID,
    mode: Mode,
    input_case_ref: str,
    draft_disposition: str | None,
    final_disposition: str | None,
    confidence_score: float | None,
    escalated: bool,
    guideline_conflict_flag: bool = False,
    explanation_ref: str | None = None,
    clinician_action: ClinicianAction | None = None,
) -> InteractionLog:
    """Always inserts a new row -- never update an existing one (Section 7)."""
    _require_consent(session, clinician_id)
    entry = InteractionLog(
        clinician_id=clinician_id,
        mode=mode,
        input_case_ref=input_case_ref,
        draft_disposition=draft_disposition,
        final_disposition=final_disposition,
        confidence_score=confidence_score,
        escalated=escalated,
        guideline_conflict_flag=guideline_conflict_flag,
        explanation_ref=explanation_ref,
        clinician_action=clinician_action,
    )
    session.add(entry)
    session.flush()
    return entry
