"""Phase J: the consent model. Four separately-named gates, checked explicitly
and first in every patient-related or recording-related endpoint -- never
inferred, never implied by a different consent type.

`require_institutional_clearance()` is the one system-wide, non-per-clinician
gate (config.py's `institutional_ethics_clearance_granted`): it has to already
be true before any doctor-level consent can unlock a patient-related action.
`require_consent()`/`record_consent()` are per-clinician, per-subject-type
(ConsentSubjectType), optionally per-session (`reference_id`) -- a doctor's own
attestation, distinct from and in addition to institutional clearance.
"""

import datetime
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.enums import ConsentSubjectType
from backend.db.models import ConsentRegistry


def require_institutional_clearance() -> None:
    if not get_settings().institutional_ethics_clearance_granted:
        raise HTTPException(
            status_code=403,
            detail=(
                "institutional ethics clearance has not been granted -- "
                "patient-related recording and uploads stay disabled until it is"
            ),
        )


def _active_consent(
    session: Session,
    clinician_id: uuid.UUID,
    subject_type: ConsentSubjectType,
    reference_id: str | None,
) -> ConsentRegistry | None:
    return (
        session.execute(
            select(ConsentRegistry)
            .where(
                ConsentRegistry.clinician_id == clinician_id,
                ConsentRegistry.subject_type == subject_type,
                ConsentRegistry.reference_id == reference_id,
                ConsentRegistry.granted_at.is_not(None),
                ConsentRegistry.revoked_at.is_(None),
            )
            .order_by(ConsentRegistry.granted_at.desc())
        )
        .scalars()
        .first()
    )


def require_consent(
    session: Session,
    clinician_id: uuid.UUID,
    subject_type: ConsentSubjectType,
    reference_id: str | None = None,
) -> None:
    """Raises 403 unless a granted, unrevoked ConsentRegistry row exists for
    this exact (clinician, subject_type, reference_id). A standing grant
    (reference_id=None) never satisfies a session-scoped check and vice versa
    -- each consent type's scope is exactly what it was recorded for."""
    if _active_consent(session, clinician_id, subject_type, reference_id) is None:
        raise HTTPException(
            status_code=403,
            detail=f"missing or revoked consent for {subject_type.value}",
        )


def record_consent(
    session: Session,
    clinician_id: uuid.UUID,
    subject_type: ConsentSubjectType,
    scope: str,
    reference_id: str | None = None,
) -> ConsentRegistry:
    consent = ConsentRegistry(
        clinician_id=clinician_id,
        subject_type=subject_type,
        scope=scope,
        reference_id=reference_id,
        granted_at=datetime.datetime.now(datetime.UTC),
    )
    session.add(consent)
    session.commit()
    return consent
