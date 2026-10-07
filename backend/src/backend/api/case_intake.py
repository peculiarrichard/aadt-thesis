"""Phase K: self-service walkthrough-case intake -- bulk upload (JSON or
.xlsx) and one-by-one form entry. No patient is involved in any of this (same
as the original walkthrough import), so the only consent gate is the
clinician's own WALKTHROUGH_RECORDING-equivalent consent -- no institutional
clearance needed, unlike Phase M's patient-related paths.

Privacy option 4: neither path saves directly anymore. Both scan (options 1+2)
and return a draft (or, for bulk, a list of drafts) for the doctor to review;
`api/case_recording.py`'s `POST /console/cases/confirm-draft` is the one place
that actually persists a case, same as the recording and de-identified-text
paths -- one save endpoint, one attestation requirement (option 3), not a
separate direct-save code path that could silently skip either.
"""

import io
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel

from backend.api.deps import ClinicianIdDep, SessionDep
from backend.db.enums import ConsentSubjectType
from backend.disposition import TO_WALKTHROUGH_LABEL
from backend.services import case_upload_parsing, consent_service
from backend.services.case_upload_parsing import FIELD_COLUMNS, CaseUploadError
from backend.services.privacy_scan import scan_fields_for_privacy_risk

router = APIRouter(prefix="/console/cases", tags=["case-intake"])

_TEMPLATE_JSON_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "walkthrough_case_template.json"
)


class CaseFormRequest(BaseModel):
    case_id: str | None = None
    case_text: str
    initial_impression: str | None = None
    questions_to_ask: list[str] | None = None
    examination_or_checks: str | None = None
    factors_toward_referral: str | None = None
    factors_against_referral: str | None = None
    flip_up: str | None = None
    flip_down: str | None = None
    red_flags: str | None = None
    confidence: str | None = None
    general_rule: str | None = None
    disposition: str
    disposition_reason: str | None = None


class ScannedDraft(BaseModel):
    case_id: str | None
    case_text: str
    initial_impression: str | None
    questions_to_ask: list[str]
    examination_or_checks: str | None
    factors_toward_referral: str | None
    factors_against_referral: str | None
    flip_up: str | None
    flip_down: str | None
    red_flags: str | None
    confidence: str | None
    general_rule: str | None
    disposition: str
    disposition_reason: str | None
    redaction_summary: dict[str, int]
    llm_flagged: bool
    llm_flag_details: str | None


class BulkScanResult(BaseModel):
    drafts: list[ScannedDraft]


def _to_scanned_draft(case_id: str | None, redacted: dict, scan) -> ScannedDraft:
    """Maps parse_record()'s DB-column-shaped output back to the walkthrough-
    JSON field names the frontend's CaseForm/DraftReview already use (shared
    with case_recording.py's draft shape) -- one draft shape everywhere,
    regardless of which path produced it."""
    return ScannedDraft(
        case_id=case_id,
        case_text=redacted["transcript_or_summary"],
        initial_impression=redacted.get("initial_impression"),
        questions_to_ask=redacted.get("questions_to_ask") or [],
        examination_or_checks=redacted.get("examination_or_checks"),
        factors_toward_referral=redacted.get("factors_toward_referral"),
        factors_against_referral=redacted.get("factors_against_referral"),
        flip_up=redacted.get("flip_up"),
        flip_down=redacted.get("flip_down"),
        red_flags=redacted.get("red_flags"),
        confidence=redacted.get("confidence_notes"),
        general_rule=redacted.get("general_rule"),
        disposition=TO_WALKTHROUGH_LABEL[redacted["doctor_disposition"]],
        disposition_reason=redacted.get("doctor_reasoning_notes"),
        redaction_summary=scan.redaction_summary,
        llm_flagged=scan.llm_flagged,
        llm_flag_details=scan.llm_flag_details,
    )


@router.get("/template")
def download_json_template() -> FileResponse:
    return FileResponse(_TEMPLATE_JSON_PATH, filename="walkthrough_case_template.json")


@router.get("/template.xlsx")
def download_xlsx_template() -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "walkthrough cases"
    sheet.append(list(FIELD_COLUMNS))
    sheet.append(
        [
            "EXAMPLE-001",
            "A short description of the presentation.",
            "Your first-pass read of the case.",
            "First question|Second question",
            "What you'd examine or check.",
            "What pushes you toward referring.",
            "What pushes you toward managing it yourself.",
            "What would escalate this.",
            "What would de-escalate this.",
            "Any danger signs.",
            "How confident you are, in your own words.",
            "The general rule this case illustrates, if any.",
            "self-care advice",
            "Why you'd give this disposition.",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=walkthrough_case_template.xlsx"},
    )


@router.post("/scan", response_model=ScannedDraft)
def scan_case_form(
    body: CaseFormRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> ScannedDraft:
    """Scans a one-by-one form submission (options 1+2) and returns it as a
    draft for review -- does not save. The frontend shows this via the same
    DraftReview component the recording/de-identified-text paths use, then
    POSTs the (possibly edited) result to `/console/cases/confirm-draft`."""
    consent_service.require_consent(session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING)
    try:
        fields = case_upload_parsing.parse_record(body.model_dump())
    except CaseUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redacted, scan = scan_fields_for_privacy_risk(fields)
    return _to_scanned_draft(body.case_id, redacted, scan)


@router.post("/bulk-upload", response_model=BulkScanResult)
async def bulk_upload_cases(
    file: UploadFile, clinician_id: ClinicianIdDep, session: SessionDep
) -> BulkScanResult:
    """Parses and scans every record in the file (options 1+2) and returns
    them all as drafts -- does not save any of them. The doctor reviews the
    whole batch, then the frontend confirms each one individually via
    `/console/cases/confirm-draft` (same attestation requirement, option 3,
    as every other path -- bulk doesn't get a shortcut around it)."""
    consent_service.require_consent(session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING)
    content = await file.read()

    try:
        if (file.filename or "").endswith(".xlsx"):
            records = case_upload_parsing.parse_bulk_xlsx(content)
        else:
            payload = json.loads(content)
            records = case_upload_parsing.parse_bulk_json(payload["cases"])
    except (CaseUploadError, json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid upload: {exc}") from exc

    drafts = []
    for fields in records:
        redacted, scan = scan_fields_for_privacy_risk(fields)
        drafts.append(_to_scanned_draft(fields.get("external_case_ref"), redacted, scan))
    return BulkScanResult(drafts=drafts)
