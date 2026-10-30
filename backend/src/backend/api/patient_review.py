"""Doctor's review queue for patient-chat consults (Phase X) -- the same
approve/correct/escalate mechanism as Consult Mode's feedback loop
(api/consult.py's give_feedback), applied to patient-originated sessions
instead of her own ad-hoc ones. This is the human-in-the-loop gate: a patient
sees the twin's draft while PENDING_DOCTOR_REVIEW, but only this endpoint
makes it final.
"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import ClinicianIdDep, SessionDep
from backend.db.enums import ClinicianAction, PatientChatStatus
from backend.db.models import Patient, PatientChatSession
from backend.services import patient_chat_service

router = APIRouter(prefix="/console/patient-chats", tags=["patient-review"])


class PendingChatSummary(BaseModel):
    session_id: str
    patient_username: str
    submitted_for_review_at: str | None
    report: dict | None


@router.get("", response_model=list[PendingChatSummary])
def list_pending(clinician_id: ClinicianIdDep, session: SessionDep) -> list[PendingChatSummary]:
    rows = session.execute(
        select(PatientChatSession, Patient.username)
        .join(Patient, Patient.patient_id == PatientChatSession.patient_id)
        .where(
            PatientChatSession.clinician_id == clinician_id,
            PatientChatSession.status == PatientChatStatus.PENDING_DOCTOR_REVIEW,
        )
        .order_by(PatientChatSession.submitted_for_review_at)
    ).all()
    return [
        PendingChatSummary(
            session_id=str(chat.session_id),
            patient_username=username,
            submitted_for_review_at=(
                chat.submitted_for_review_at.isoformat() if chat.submitted_for_review_at else None
            ),
            report=chat.draft_report,
        )
        for chat, username in rows
    ]


class ChatTranscriptMessage(BaseModel):
    role: str
    content: str


class PendingChatDetail(PendingChatSummary):
    transcript: list[ChatTranscriptMessage]


@router.get("/{session_id}", response_model=PendingChatDetail)
def get_pending_detail(
    session_id: uuid.UUID, clinician_id: ClinicianIdDep, session: SessionDep
) -> PendingChatDetail:
    chat = patient_chat_service.get_session_for_clinician(session, clinician_id, session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    patient = session.get(Patient, chat.patient_id)
    messages = patient_chat_service.list_messages(session, session_id)
    return PendingChatDetail(
        session_id=str(chat.session_id),
        patient_username=patient.username,
        submitted_for_review_at=(
            chat.submitted_for_review_at.isoformat() if chat.submitted_for_review_at else None
        ),
        report=chat.draft_report,
        transcript=[ChatTranscriptMessage(role=m.role.value, content=m.content) for m in messages],
    )


class ReviewRequest(BaseModel):
    action: ClinicianAction
    corrected_disposition: str | None = None
    corrected_reasoning: str | None = None
    correction_notes: str | None = None


class ReviewResponse(BaseModel):
    resolved: bool
    new_case_id: str | None


@router.post("/{session_id}/review", response_model=ReviewResponse)
def review(
    session_id: uuid.UUID, body: ReviewRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> ReviewResponse:
    chat = patient_chat_service.get_session_for_clinician(session, clinician_id, session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    if chat.status != PatientChatStatus.PENDING_DOCTOR_REVIEW:
        raise HTTPException(status_code=400, detail="this consult isn't awaiting review")

    try:
        new_case_id = patient_chat_service.resolve_review(
            session,
            clinician_id,
            chat,
            body.action,
            body.corrected_disposition,
            body.corrected_reasoning,
            body.correction_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewResponse(resolved=True, new_case_id=new_case_id)
