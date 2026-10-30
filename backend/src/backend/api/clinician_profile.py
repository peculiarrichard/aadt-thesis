"""The doctor's own view of her twin's profile/stats (Phase V) -- the same
shape patients see on the directory (api/patient_directory.py), plus edit
access to the fields she controls (specialty/hospital/location)."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import ClinicianIdDep, SessionDep
from backend.services import twin_profile_service

router = APIRouter(prefix="/console/profile", tags=["clinician-profile"])


class ProfileUpdate(BaseModel):
    specialty: str | None = None
    hospital: str | None = None
    location: str | None = None


class TwinProfile(BaseModel):
    clinician_id: str
    name: str
    specialty: str | None
    hospital: str | None
    location: str | None
    patients_attended: int
    average_confidence: float | None
    review_count: int
    average_rating: float | None


@router.get("", response_model=TwinProfile)
def get_my_profile(clinician_id: ClinicianIdDep, session: SessionDep) -> TwinProfile:
    return TwinProfile(**twin_profile_service.get_twin_profile(session, clinician_id))


@router.patch("", response_model=TwinProfile)
def update_my_profile(
    body: ProfileUpdate, clinician_id: ClinicianIdDep, session: SessionDep
) -> TwinProfile:
    twin_profile_service.update_profile(
        session, clinician_id, body.specialty, body.hospital, body.location
    )
    return TwinProfile(**twin_profile_service.get_twin_profile(session, clinician_id))
