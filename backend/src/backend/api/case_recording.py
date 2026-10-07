"""Phase M: recording pipelines (walkthrough + live patient consultation) and
de-identified-case text upload. All three converge on the same structuring
agent (Phase L) and the same review-before-save UX -- they differ only in
which consent gate applies and whether de-identification runs.

Patient-related endpoints here always check `require_institutional_clearance`
first, then the specific per-doctor consent -- institutional clearance alone
is never sufficient, and neither is a doctor's own consent alone.
"""

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.agents.case_structuring_agent import CaseStructuringParseError, draft_structured_case
from backend.api.deps import ClinicianIdDep, SessionDep
from backend.db.enums import AuditActor, ConsentSubjectType, SourceType
from backend.db.models import AuditLog
from backend.services import consent_service, data_services
from backend.services.privacy_scan import scan_fields_for_privacy_risk, scan_for_privacy_risk

router = APIRouter(prefix="/console/cases", tags=["case-recording"])


class StructuredDraftResponse(BaseModel):
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
    disposition: str | None
    disposition_reason: str | None
    redaction_summary: dict[str, int]
    llm_flagged: bool
    llm_flag_details: str | None
    raw_transcript: str


def _structure_text(raw_text: str) -> tuple[dict, str]:
    """Returns (draft-as-dict, parse_error_message_or_empty). Never raises --
    a failed extraction still hands the raw text back so nothing is lost; the
    doctor fills the structured fields in herself in that case."""
    try:
        draft = draft_structured_case(raw_text)
    except CaseStructuringParseError:
        return (
            {
                "case_text": raw_text,
                "initial_impression": None,
                "questions_to_ask": [],
                "examination_or_checks": None,
                "factors_toward_referral": None,
                "factors_against_referral": None,
                "flip_up": None,
                "flip_down": None,
                "red_flags": None,
                "confidence": None,
                "general_rule": None,
                "disposition": None,
                "disposition_reason": None,
            },
            "auto-structuring failed; fill in the fields yourself from the transcript below",
        )
    return (
        {
            "case_text": draft.case_text,
            "initial_impression": draft.initial_impression,
            "questions_to_ask": draft.questions_to_ask,
            "examination_or_checks": draft.examination_or_checks,
            "factors_toward_referral": draft.factors_toward_referral,
            "factors_against_referral": draft.factors_against_referral,
            "flip_up": draft.flip_up,
            "flip_down": draft.flip_down,
            "red_flags": draft.red_flags,
            "confidence": draft.confidence,
            "general_rule": draft.general_rule,
            "disposition": draft.disposition,
            "disposition_reason": draft.disposition_reason,
        },
        "",
    )


@router.post("/recordings", response_model=StructuredDraftResponse)
async def upload_recording(
    clinician_id: ClinicianIdDep,
    session: SessionDep,
    audio: UploadFile,
    kind: Literal["walkthrough", "patient_consultation"] = Form(...),
    session_reference_id: str | None = Form(default=None),
) -> StructuredDraftResponse:
    if kind == "walkthrough":
        consent_service.require_consent(
            session, clinician_id, ConsentSubjectType.WALKTHROUGH_RECORDING
        )
    else:
        consent_service.require_institutional_clearance()
        if not session_reference_id:
            raise HTTPException(
                status_code=400,
                detail="session_reference_id is required for a patient consultation recording",
            )
        consent_service.require_consent(
            session,
            clinician_id,
            ConsentSubjectType.PATIENT_RECORDING_SESSION,
            reference_id=session_reference_id,
        )

    # Deferred: faster-whisper is heavy (same reasoning as BGE-M3 elsewhere in
    # this project) -- never imported at module level.
    from backend.transcription.whisper_backend import transcribe_audio

    audio_bytes = await audio.read()
    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)
    try:
        transcript = transcribe_audio(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    # Privacy option 1: this scan runs for every recording, walkthrough
    # included -- walkthrough narration isn't supposed to involve a real
    # patient, but nothing about what a doctor actually says guarantees that,
    # so this is a safety net rather than a redundant check on top of
    # whatever's already true by assumption.
    scan = scan_for_privacy_risk(transcript)

    fields, error = _structure_text(scan.text)
    if error:
        raise HTTPException(status_code=502, detail=error)

    return StructuredDraftResponse(
        **fields,
        redaction_summary=scan.redaction_summary,
        llm_flagged=scan.llm_flagged,
        llm_flag_details=scan.llm_flag_details,
        raw_transcript=scan.text,
    )


class DeidentifiedTextRequest(BaseModel):
    text: str


@router.post("/from-deidentified-text", response_model=StructuredDraftResponse)
def upload_deidentified_text(
    body: DeidentifiedTextRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> StructuredDraftResponse:
    consent_service.require_institutional_clearance()
    consent_service.require_consent(session, clinician_id, ConsentSubjectType.PATIENT_DATA_BATCH)

    # Defense in depth: always re-run de-identification even though the
    # doctor is attesting this text is already de-identified -- never trust a
    # single redaction pass.
    scan = scan_for_privacy_risk(body.text)

    fields, error = _structure_text(scan.text)
    if error:
        raise HTTPException(status_code=502, detail=error)

    return StructuredDraftResponse(
        **fields,
        redaction_summary=scan.redaction_summary,
        llm_flagged=scan.llm_flagged,
        llm_flag_details=scan.llm_flag_details,
        raw_transcript=scan.text,
    )


class ConfirmDraftRequest(BaseModel):
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
    source_type: Literal["walkthrough", "real_consultation"]
    # Privacy option 3: a per-case attestation, separate from the standing
    # consent captured once at the start of this flow (ConsentGate) -- every
    # individual save needs its own explicit confirmation, not just one
    # blanket consent covering everything that follows it.
    attestation_confirmed: bool = False


class ConfirmDraftResponse(BaseModel):
    case_id: str
    redaction_summary: dict[str, int]


@router.post("/confirm-draft", response_model=ConfirmDraftResponse)
def confirm_draft(
    body: ConfirmDraftRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> ConfirmDraftResponse:
    """Finalizes a doctor-reviewed draft (from either recording path, the
    de-identified-text path, or the form/bulk-upload scan-and-review path)
    into a real Case row. Nothing upstream of this endpoint ever writes to
    the database -- review-before-save, always.

    Re-scans the final (possibly hand-edited) text rather than trusting
    whatever scan produced the draft the doctor started from -- an edit
    after that scan is exactly the case the first scan couldn't have caught.
    Regex redaction always applies, unconditionally, to whatever gets saved;
    the LLM flag is advisory and doesn't block, but `attestation_confirmed`
    is required regardless of whether anything was flagged -- the explicit
    per-case confirmation this option asked for, not just a consequence of
    passing or failing the automated check.
    """
    if not body.attestation_confirmed:
        raise HTTPException(
            status_code=400,
            detail="attestation_confirmed must be true: confirm this case does not "
            "reference a real, identifiable patient before it can be saved.",
        )

    from backend.services.case_upload_parsing import CaseUploadError, parse_record

    try:
        fields = parse_record(body.model_dump())
    except CaseUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redacted_fields, scan = scan_fields_for_privacy_risk(fields)

    source_type = (
        SourceType.WALKTHROUGH
        if body.source_type == "walkthrough"
        else SourceType.REAL_CONSULTATION
    )
    case = data_services.create_case(
        session, clinician_id, source_type=source_type, **redacted_fields
    )
    session.add(
        AuditLog(
            clinician_id=clinician_id,
            actor=AuditActor.CLINICIAN,
            action=("case_saved_with_privacy_flag" if scan.requires_review else "case_saved"),
            reference_table="cases",
            reference_id=str(case.case_id),
        )
    )
    session.commit()
    return ConfirmDraftResponse(case_id=str(case.case_id), redaction_summary=scan.redaction_summary)
