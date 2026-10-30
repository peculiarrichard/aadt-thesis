"""Patient-chat session lifecycle (Phase W/X, simulated patients only):
create, append messages, run the twin once intake is done, and resolve on the
doctor's review action. Mirrors api/consult.py's ad-hoc-consult +
approve/correct/escalate pattern, applied to patient-originated sessions that
must persist their transcript/report server-side (see PatientChatSession's
docstring) and sit behind a pending-review gate before the patient sees a
final result.
"""

import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.agents.report_builder import ClericalDetails, DoctorReport, build_doctor_report
from backend.agents.twin_agent import FULL_SYSTEM, run_twin_agent
from backend.db.enums import ChatRole, ClinicianAction, Mode, PatientChatStatus, SourceType
from backend.db.models import Clinician, PatientChatMessage, PatientChatSession
from backend.disposition import FROM_WALKTHROUGH_LABEL
from backend.services import data_services


def create_session(
    session: Session,
    patient_id: uuid.UUID,
    clinician_id: uuid.UUID,
    presenting_complaint: str,
    clerical: ClericalDetails,
) -> PatientChatSession:
    chat = PatientChatSession(
        patient_id=patient_id,
        clinician_id=clinician_id,
        status=PatientChatStatus.IN_PROGRESS,
        patient_age=clerical.age,
        patient_sex=clerical.sex,
        temperature=clerical.temperature,
        blood_pressure=clerical.blood_pressure,
        pulse_rate=clerical.pulse_rate,
        respiratory_rate=clerical.respiratory_rate,
        oxygen_saturation=clerical.oxygen_saturation,
        case_text=presenting_complaint,
    )
    session.add(chat)
    session.flush()
    session.add(
        PatientChatMessage(
            session_id=chat.session_id, role=ChatRole.PATIENT, content=presenting_complaint
        )
    )
    session.commit()
    return chat


def get_session_for_patient(
    session: Session, patient_id: uuid.UUID, session_id: uuid.UUID
) -> PatientChatSession | None:
    return session.execute(
        select(PatientChatSession).where(
            PatientChatSession.session_id == session_id,
            PatientChatSession.patient_id == patient_id,
        )
    ).scalar_one_or_none()


def get_session_for_clinician(
    session: Session, clinician_id: uuid.UUID, session_id: uuid.UUID
) -> PatientChatSession | None:
    return session.execute(
        select(PatientChatSession).where(
            PatientChatSession.session_id == session_id,
            PatientChatSession.clinician_id == clinician_id,
        )
    ).scalar_one_or_none()


def list_messages(session: Session, session_id: uuid.UUID) -> list[PatientChatMessage]:
    return list(
        session.execute(
            select(PatientChatMessage)
            .where(PatientChatMessage.session_id == session_id)
            .order_by(PatientChatMessage.created_at)
        )
        .scalars()
        .all()
    )


def append_message(
    session: Session, session_id: uuid.UUID, role: ChatRole, content: str
) -> PatientChatMessage:
    message = PatientChatMessage(session_id=session_id, role=role, content=content)
    session.add(message)
    session.commit()
    return message


def question_count(session: Session, session_id: uuid.UUID) -> int:
    return session.execute(
        select(func.count())
        .select_from(PatientChatMessage)
        .where(
            PatientChatMessage.session_id == session_id, PatientChatMessage.role == ChatRole.TWIN
        )
    ).scalar_one()


def _report_to_dict(report: DoctorReport) -> dict:
    return {
        "generated_at": report.generated_at.isoformat(),
        "clinician_name": report.clinician_name,
        "patient_reference": report.clerical.patient_reference,
        "patient_age": report.clerical.age,
        "patient_sex": report.clerical.sex,
        "temperature": report.clerical.temperature,
        "blood_pressure": report.clerical.blood_pressure,
        "pulse_rate": report.clerical.pulse_rate,
        "respiratory_rate": report.clerical.respiratory_rate,
        "oxygen_saturation": report.clerical.oxygen_saturation,
        "presenting_complaint": report.presenting_complaint,
        "history_and_impression": report.history_and_impression,
        "guideline_considerations": report.guideline_considerations,
        "assessment": report.assessment,
        "plan": report.plan,
        "disclaimer": report.disclaimer,
    }


def complete_intake(
    session: Session,
    chat: PatientChatSession,
    case_summary: str,
    patient_username: str,
) -> None:
    """Runs the twin once intake is done, persists the draft report, and
    flips status to PENDING_DOCTOR_REVIEW -- the human-in-the-loop gate."""
    clinician_id = chat.clinician_id
    output = run_twin_agent(session, clinician_id, case_summary, FULL_SYSTEM)
    clinician = session.get(Clinician, clinician_id)

    entry = data_services.create_interaction_log_entry(
        session,
        clinician_id,
        mode=Mode.PATIENT_CONSULT,
        input_case_ref=f"patient-chat-{chat.session_id}",
        draft_disposition=output.draft_disposition.value,
        final_disposition=output.disposition.value,
        confidence_score=output.confidence,
        escalated=output.escalated,
        model_version=output.config_label,
    )

    report = build_doctor_report(
        clinician.name,
        case_summary,
        ClericalDetails(
            patient_reference=patient_username,
            age=chat.patient_age,
            sex=chat.patient_sex,
            temperature=chat.temperature,
            blood_pressure=chat.blood_pressure,
            pulse_rate=chat.pulse_rate,
            respiratory_rate=chat.respiratory_rate,
            oxygen_saturation=chat.oxygen_saturation,
        ),
        output,
    )

    chat.case_text = case_summary
    chat.interaction_id = entry.interaction_id
    chat.draft_report = _report_to_dict(report)
    chat.status = PatientChatStatus.PENDING_DOCTOR_REVIEW
    chat.submitted_for_review_at = datetime.datetime.now(datetime.UTC)
    session.commit()


def resolve_review(
    session: Session,
    clinician_id: uuid.UUID,
    chat: PatientChatSession,
    action: ClinicianAction,
    corrected_disposition: str | None,
    corrected_reasoning: str | None,
    correction_notes: str | None,
) -> str | None:
    """Mirrors api/consult.py's give_feedback branches. Returns the new
    Case's id if one was created (CORRECTED only). Raises ValueError on an
    invalid corrected_disposition -- callers turn that into a 400."""
    new_case_id: str | None = None
    final_report = dict(chat.draft_report or {})

    if action == ClinicianAction.CORRECTED:
        valid = corrected_disposition in FROM_WALKTHROUGH_LABEL
        if not corrected_disposition or not valid:
            raise ValueError(
                f"corrected_disposition must be one of {sorted(FROM_WALKTHROUGH_LABEL)}"
            )
        disposition = FROM_WALKTHROUGH_LABEL[corrected_disposition]

        case = data_services.create_case(
            session,
            clinician_id,
            transcript_or_summary=chat.case_text or "",
            source_type=SourceType.PATIENT_CHAT_FEEDBACK,
            doctor_disposition=disposition.value,
            doctor_reasoning_notes=corrected_reasoning,
        )
        session.flush()

        from backend.db.embed_walkthrough_cases import embed_single_case

        embed_single_case(session, clinician_id, case)
        new_case_id = str(case.case_id)

        final_report["assessment"] = (
            f"Reviewed and corrected by the doctor. Disposition: {corrected_disposition}."
        )
        final_report["plan"] = corrected_reasoning or final_report.get("plan", "")
    elif action == ClinicianAction.ESCALATED_REVIEW:
        final_report["assessment"] = "Escalated by the doctor for specialist review."
        final_report["plan"] = "Pending specialist review."
    # APPROVED: final_report stays identical to the draft.

    chat.final_report = final_report
    chat.clinician_action = action
    chat.clinician_correction_notes = correction_notes
    chat.status = PatientChatStatus.RESOLVED
    chat.resolved_at = datetime.datetime.now(datetime.UTC)

    if chat.interaction_id is not None:
        data_services.record_clinician_feedback(
            session, clinician_id, chat.interaction_id, action, correction_notes
        )

    session.commit()
    return new_case_id
