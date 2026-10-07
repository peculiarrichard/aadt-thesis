"""Layer 6.2 data services (Section 5.6.2): cases/interaction_log, scoped
by clinician_id + consent (reuses Connector's policy check)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.enums import ClinicianAction, Mode, SourceType
from backend.db.models import Case, CasePrecedentVector, InteractionLog
from backend.services.connector import Connector


def _require_consent(session: Session, clinician_id: uuid.UUID) -> None:
    Connector(session, clinician_id).authorize()


def list_cases(session: Session, clinician_id: uuid.UUID) -> list[Case]:
    _require_consent(session, clinician_id)
    return session.execute(select(Case).where(Case.clinician_id == clinician_id)).scalars().all()


_QUALIFYING_SOURCE_TYPES = (
    SourceType.WALKTHROUGH,
    SourceType.ELICITATION_SESSION,
    SourceType.REAL_CONSULTATION,
    SourceType.CONSULT_FEEDBACK,
)


def count_qualifying_cases(session: Session, clinician_id: uuid.UUID) -> int:
    """How many of this clinician's cases count toward the Phase N
    minimum-case gate (config.min_cases_to_build_twin). By the time a Case row
    exists, it's already walkthrough data, de-identified real-consultation
    data (Phase M's gates run before any row is written), or a consult
    correction (Phase O) -- nothing unqualified ever reaches this table, so
    every source_type qualifies except none currently excluded; the explicit
    tuple exists so a future new SourceType doesn't silently start counting
    without a decision."""
    _require_consent(session, clinician_id)
    return session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            Case.clinician_id == clinician_id,
            Case.source_type.in_(_QUALIFYING_SOURCE_TYPES),
        )
    ).scalar_one()


def has_precedent_memory(session: Session, clinician_id: uuid.UUID) -> bool:
    """True once at least one case has been embedded (Phase N's "already
    built" check, also gating Phase O's ad-hoc consult)."""
    _require_consent(session, clinician_id)
    return (
        session.execute(
            select(CasePrecedentVector.vector_id)
            .where(CasePrecedentVector.clinician_id == clinician_id)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def get_case(session: Session, clinician_id: uuid.UUID, case_id: uuid.UUID) -> Case | None:
    """None both when the case doesn't exist and when it belongs to another
    clinician -- tenant isolation, same as list_cases's WHERE-scoping, not a
    separate ownership check a caller could forget."""
    _require_consent(session, clinician_id)
    return session.execute(
        select(Case).where(Case.case_id == case_id, Case.clinician_id == clinician_id)
    ).scalar_one_or_none()


def create_case(
    session: Session,
    clinician_id: uuid.UUID,
    transcript_or_summary: str,
    source_type: SourceType,
    doctor_disposition: str | None = None,
    doctor_reasoning_notes: str | None = None,
    external_case_ref: str | None = None,
    used_for_training: bool = True,
    initial_impression: str | None = None,
    questions_to_ask: list[str] | None = None,
    examination_or_checks: str | None = None,
    factors_toward_referral: str | None = None,
    factors_against_referral: str | None = None,
    flip_up: str | None = None,
    flip_down: str | None = None,
    red_flags: str | None = None,
    confidence_notes: str | None = None,
    general_rule: str | None = None,
) -> Case:
    """The extra structured fields (initial_impression onward) mirror the
    walkthrough JSON shape (db/import_walkthrough_cases.py's _case_from_record)
    -- the self-service upload/form/recording paths (Phase K/M) populate them
    through here instead of duplicating the field list."""
    _require_consent(session, clinician_id)
    case = Case(
        clinician_id=clinician_id,
        transcript_or_summary=transcript_or_summary,
        source_type=source_type,
        doctor_disposition=doctor_disposition,
        doctor_reasoning_notes=doctor_reasoning_notes,
        external_case_ref=external_case_ref,
        used_for_training=used_for_training,
        initial_impression=initial_impression,
        questions_to_ask=questions_to_ask,
        examination_or_checks=examination_or_checks,
        factors_toward_referral=factors_toward_referral,
        factors_against_referral=factors_against_referral,
        flip_up=flip_up,
        flip_down=flip_down,
        red_flags=red_flags,
        confidence_notes=confidence_notes,
        general_rule=general_rule,
    )
    session.add(case)
    session.flush()
    return case


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
    model_version: str | None = None,
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
        model_version=model_version,
    )
    session.add(entry)
    session.flush()
    return entry


def get_interaction_log_entry(
    session: Session, clinician_id: uuid.UUID, interaction_id: uuid.UUID
) -> InteractionLog | None:
    _require_consent(session, clinician_id)
    return session.execute(
        select(InteractionLog).where(
            InteractionLog.interaction_id == interaction_id,
            InteractionLog.clinician_id == clinician_id,
        )
    ).scalar_one_or_none()


def record_clinician_feedback(
    session: Session,
    clinician_id: uuid.UUID,
    interaction_id: uuid.UUID,
    clinician_action: ClinicianAction,
    clinician_correction_notes: str | None = None,
) -> InteractionLog | None:
    """The one legitimate update to an existing interaction_log row: Section
    7's "never overwritten" protects the twin's own draft/final disposition,
    not the clinician_action/clinician_correction_notes fields, which exist
    specifically to record her later verdict on an interaction already
    logged. Returns None (no-op) if the interaction doesn't exist or belongs
    to another clinician."""
    entry = get_interaction_log_entry(session, clinician_id, interaction_id)
    if entry is None:
        return None
    entry.clinician_action = clinician_action
    entry.clinician_correction_notes = clinician_correction_notes
    session.flush()
    return entry
