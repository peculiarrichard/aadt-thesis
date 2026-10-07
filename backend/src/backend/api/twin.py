"""Phase N: the minimum-case gate before a clinician can build her twin, and
the build action itself. "Build" means embedding her qualifying cases into
precedent memory (db/embed_walkthrough_cases.py) -- there is no training
step, consistent with the rest of this system's design.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.deps import ClinicianIdDep, SessionDep
from backend.config import get_settings
from backend.services import data_services

router = APIRouter(prefix="/console/twin", tags=["twin"])


class TwinStatus(BaseModel):
    qualifying_case_count: int
    min_cases_required: int
    ready_to_build: bool
    already_built: bool


class BuildTwinResult(BaseModel):
    embedded_count: int


def _status(session: SessionDep, clinician_id: ClinicianIdDep) -> TwinStatus:
    count = data_services.count_qualifying_cases(session, clinician_id)
    threshold = get_settings().min_cases_to_build_twin
    already_built = data_services.has_precedent_memory(session, clinician_id)
    return TwinStatus(
        qualifying_case_count=count,
        min_cases_required=threshold,
        ready_to_build=count >= threshold,
        already_built=already_built,
    )


@router.get("/status", response_model=TwinStatus)
def get_twin_status(clinician_id: ClinicianIdDep, session: SessionDep) -> TwinStatus:
    return _status(session, clinician_id)


@router.post("/build", response_model=BuildTwinResult)
def build_twin(clinician_id: ClinicianIdDep, session: SessionDep) -> BuildTwinResult:
    status = _status(session, clinician_id)
    if not status.ready_to_build:
        needed = status.min_cases_required - status.qualifying_case_count
        raise HTTPException(
            status_code=400,
            detail=(
                f"{needed} more qualifying case(s) needed before building your twin "
                f"({status.qualifying_case_count}/{status.min_cases_required})"
            ),
        )

    from backend.db.embed_walkthrough_cases import embed_walkthrough_cases

    count = embed_walkthrough_cases(session=session, clinician_id=clinician_id)
    return BuildTwinResult(embedded_count=count)
