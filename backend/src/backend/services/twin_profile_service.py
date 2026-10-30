"""Twin profile/stats, shown both to the doctor (console) and to patients
(the directory, api/patient_directory.py) in the same shape (Phase V).
Not clinician_id-consent-scoped like data_services.py's functions -- a
directory listing is deliberately readable by any logged-in patient, and the
doctor's own profile view/edit needs no additional gate beyond her session.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.enums import Mode
from backend.db.models import Clinician, InteractionLog, PatientChatSession, Review


def get_twin_profile(session: Session, clinician_id: uuid.UUID) -> dict:
    clinician = session.get(Clinician, clinician_id)

    patients_attended = session.execute(
        select(func.count())
        .select_from(PatientChatSession)
        .where(PatientChatSession.clinician_id == clinician_id)
    ).scalar_one()

    average_confidence = session.execute(
        select(func.avg(InteractionLog.confidence_score)).where(
            InteractionLog.clinician_id == clinician_id,
            InteractionLog.mode == Mode.PATIENT_CONSULT,
        )
    ).scalar_one()

    review_count = session.execute(
        select(func.count()).select_from(Review).where(Review.clinician_id == clinician_id)
    ).scalar_one()

    average_rating = session.execute(
        select(func.avg(Review.rating)).where(Review.clinician_id == clinician_id)
    ).scalar_one()

    return {
        "clinician_id": str(clinician_id),
        "name": clinician.name,
        "specialty": clinician.specialty,
        "hospital": clinician.hospital,
        "location": clinician.location,
        "patients_attended": patients_attended,
        "average_confidence": float(average_confidence) if average_confidence is not None else None,
        "review_count": review_count,
        "average_rating": float(average_rating) if average_rating is not None else None,
    }


def update_profile(
    session: Session,
    clinician_id: uuid.UUID,
    specialty: str | None,
    hospital: str | None,
    location: str | None,
) -> None:
    clinician = session.get(Clinician, clinician_id)
    if specialty is not None:
        clinician.specialty = specialty
    if hospital is not None:
        clinician.hospital = hospital
    if location is not None:
        clinician.location = location
    session.commit()
