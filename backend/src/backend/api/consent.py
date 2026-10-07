"""Phase J: where a doctor's consent screens POST to. Each subject_type is its
own clearly separate action -- the frontend shows one explicit screen per
type, never a single generic "I consent" checkbox. See
services/consent_service.py for the enforcement side (require_consent).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import ClinicianIdDep, SessionDep
from backend.db.enums import ConsentSubjectType
from backend.services import consent_service

router = APIRouter(prefix="/console/consent", tags=["consent"])


class ConsentRequest(BaseModel):
    subject_type: ConsentSubjectType
    scope: str
    reference_id: str | None = None


class ConsentResponse(BaseModel):
    consent_id: str
    subject_type: ConsentSubjectType
    reference_id: str | None


@router.post("", response_model=ConsentResponse)
def grant_consent(
    body: ConsentRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> ConsentResponse:
    consent = consent_service.record_consent(
        session, clinician_id, body.subject_type, body.scope, body.reference_id
    )
    return ConsentResponse(
        consent_id=str(consent.consent_id),
        subject_type=consent.subject_type,
        reference_id=consent.reference_id,
    )
