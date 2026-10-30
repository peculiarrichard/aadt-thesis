"""Patient-facing directory of consenting doctors' twins (Phase V) -- a
single clinician today, shaped as a list so it generalizes later without an
API change. Reviews are tied to a resolved chat session, not a drive-by
rating untethered from an actual consult."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import PatientIdDep, SessionDep
from backend.db.enums import PatientChatStatus
from backend.db.models import Clinician, PatientChatSession, Review
from backend.services import twin_profile_service

router = APIRouter(prefix="/patient", tags=["patient-directory"])


class TwinProfileOut(BaseModel):
    clinician_id: str
    name: str
    specialty: str | None
    hospital: str | None
    location: str | None
    patients_attended: int
    average_confidence: float | None
    review_count: int
    average_rating: float | None


@router.get("/clinicians", response_model=list[TwinProfileOut])
def list_clinicians(patient_id: PatientIdDep, session: SessionDep) -> list[TwinProfileOut]:
    del patient_id  # auth-only: confirms a logged-in patient, not scoping the query
    clinician_ids = session.execute(select(Clinician.clinician_id)).scalars().all()
    return [
        TwinProfileOut(**twin_profile_service.get_twin_profile(session, cid))
        for cid in clinician_ids
    ]


class ReviewRequest(BaseModel):
    patient_chat_session_id: str
    rating: int
    comment: str | None = None


class ReviewResponse(BaseModel):
    review_id: str


@router.post("/clinicians/{clinician_id}/reviews", response_model=ReviewResponse)
def leave_review(
    clinician_id: uuid.UUID, body: ReviewRequest, patient_id: PatientIdDep, session: SessionDep
) -> ReviewResponse:
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")

    chat = session.execute(
        select(PatientChatSession).where(
            PatientChatSession.session_id == uuid.UUID(body.patient_chat_session_id),
            PatientChatSession.patient_id == patient_id,
            PatientChatSession.clinician_id == clinician_id,
        )
    ).scalar_one_or_none()
    if chat is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    if chat.status != PatientChatStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="can only review a resolved consult")

    existing = session.execute(
        select(Review).where(Review.patient_chat_session_id == chat.session_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="you've already reviewed this consult")

    review = Review(
        clinician_id=clinician_id,
        patient_id=patient_id,
        patient_chat_session_id=chat.session_id,
        rating=body.rating,
        comment=body.comment,
    )
    session.add(review)
    session.commit()
    return ReviewResponse(review_id=str(review.review_id))
