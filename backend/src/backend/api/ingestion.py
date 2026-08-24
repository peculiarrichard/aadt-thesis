"""Layer 2 ingestion API (Section 5.2): "a simple ingestion API with retry and
local queuing before upload, so that a dropped connection during upload does not
lose a consultation transcript."

Scope boundary, stated explicitly: "local queuing" in the doc's sense is a
client-side responsibility (the intake tooling buffers a transcript until it gets
a confirmed success response) that belongs to the console (Layer 8, not yet
built). What this module builds is the server-side half that makes client
retries safe: an idempotent upload endpoint backed by durable staging
(`ingestion_queue`), so a client that resends the same upload after a dropped
connection gets back the original result instead of creating a duplicate or
losing data.

This endpoint does not write to `consultations` — per Section 6.1, that's the
job of the DDT management agents (Layer 7.1, not yet built), which read from
`ingestion_queue`.

Security controls added per docs/security_review.md items 1-4: a shared service
API key (backend.api.auth), de-identification before storage, a consent-status
check, and an audit_log write on every accepted upload.
"""

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.auth import require_service_api_key
from backend.db.enums import AuditActor, IngestionStatus, SourceType
from backend.db.models import AuditLog, Clinician, IngestionQueueItem
from backend.db.session import get_session
from backend.deidentify import RedactionSpan, deidentify_text

router = APIRouter(
    prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(require_service_api_key)]
)

SessionDep = Annotated[Session, Depends(get_session)]

# The consent value that permits ingestion. clinicians.consent_status is a free-text
# column (Section 7 doesn't define an enum for it) — this is this project's own
# convention for what counts as "consented", not something the design doc specifies.
_CONSENTED_STATUS = "granted"


class TranscriptUploadRequest(BaseModel):
    clinician_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    content: str = Field(min_length=1, max_length=200_000)


class TranscriptUploadResponse(BaseModel):
    ingestion_id: uuid.UUID
    clinician_id: uuid.UUID
    source_type: SourceType
    status: IngestionStatus
    received_at: datetime.datetime
    idempotent_replay: bool
    redaction_summary: dict[str, int]


@router.post(
    "/transcripts",
    response_model=TranscriptUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_transcript(
    body: TranscriptUploadRequest,
    response: Response,
    session: SessionDep,
) -> TranscriptUploadResponse:
    clinician = session.get(Clinician, body.clinician_id)
    if clinician is None:
        raise HTTPException(status_code=404, detail="clinician not found")

    if clinician.consent_status != _CONSENTED_STATUS:
        raise HTTPException(
            status_code=403, detail="clinician has not granted consent for data ingestion"
        )

    deidentified = deidentify_text(body.content)
    redaction_summary = _summarize_redactions(deidentified.redactions)

    existing = session.execute(
        select(IngestionQueueItem).where(
            IngestionQueueItem.clinician_id == body.clinician_id,
            IngestionQueueItem.idempotency_key == body.idempotency_key,
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.content != deidentified.text or existing.source_type != body.source_type:
            raise HTTPException(
                status_code=409,
                detail="idempotency_key was already used with different content or source_type",
            )
        _write_audit_log(
            session,
            clinician_id=body.clinician_id,
            action="ingestion_upload_replay",
            reference_id=existing.ingestion_id,
        )
        session.commit()
        response.status_code = status.HTTP_200_OK
        return _to_response(existing, idempotent_replay=True)

    item = IngestionQueueItem(
        clinician_id=body.clinician_id,
        idempotency_key=body.idempotency_key,
        source_type=body.source_type,
        content=deidentified.text,
        redaction_summary=redaction_summary,
    )
    session.add(item)
    session.flush()
    _write_audit_log(
        session,
        clinician_id=body.clinician_id,
        action="ingestion_upload",
        reference_id=item.ingestion_id,
    )
    session.commit()
    session.refresh(item)
    return _to_response(item, idempotent_replay=False)


@router.get("/transcripts", response_model=list[TranscriptUploadResponse])
def list_transcripts(
    clinician_id: uuid.UUID,
    session: SessionDep,
) -> list[TranscriptUploadResponse]:
    items = (
        session.execute(
            select(IngestionQueueItem).where(IngestionQueueItem.clinician_id == clinician_id)
        )
        .scalars()
        .all()
    )
    return [_to_response(item, idempotent_replay=False) for item in items]


def _summarize_redactions(redactions: list[RedactionSpan]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for redaction in redactions:
        summary[redaction.category] = summary.get(redaction.category, 0) + 1
    return summary


def _write_audit_log(
    session: Session, *, clinician_id: uuid.UUID, action: str, reference_id: uuid.UUID
) -> None:
    session.add(
        AuditLog(
            clinician_id=clinician_id,
            actor=AuditActor.SYSTEM,
            action=action,
            reference_table="ingestion_queue",
            reference_id=str(reference_id),
        )
    )


def _to_response(item: IngestionQueueItem, idempotent_replay: bool) -> TranscriptUploadResponse:
    return TranscriptUploadResponse(
        ingestion_id=item.ingestion_id,
        clinician_id=item.clinician_id,
        source_type=item.source_type,
        status=item.status,
        received_at=item.received_at,
        idempotent_replay=idempotent_replay,
        redaction_summary=item.redaction_summary,
    )
