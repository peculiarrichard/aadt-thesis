"""Imports structured walkthrough cases (same schema as
backend/data/walkthrough_cases_structured.json) for a clinician -- bypasses
the ingestion API and de-identification entirely: walkthrough data isn't PHI
and doesn't need redaction or consent-gating beyond the clinician's own
WALKTHROUGH_RECORDING-equivalent consent (Phase J), since no patient is
involved.

Generic per clinician (Phase I) -- pass `clinician_id` for any doctor; the old
WALKTHROUGH_CLINICIAN_NAME/_EMAIL lookup is kept only as the default fallback
for the pilot doctor's own scripts and tests, not a hardcoded assumption any
new caller has to live with.

Idempotent: clears and re-inserts that one clinician's cases on each run
(scoped by clinician_id), not a blanket table delete -- other clinicians' data
must survive a re-run.
"""

import json
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.enums import SourceType
from backend.db.models import Case, CasePrecedentVector, Clinician
from backend.db.session import SessionLocal
from backend.disposition import FROM_WALKTHROUGH_LABEL

WALKTHROUGH_CLINICIAN_NAME = "Consenting GP (walkthrough study)"
DEFAULT_JSON_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "walkthrough_cases_structured.json"
)


def _get_clinician(session: Session, clinician_id: uuid.UUID) -> Clinician:
    clinician = session.get(Clinician, clinician_id)
    if clinician is None:
        raise ValueError(f"unknown clinician {clinician_id}")
    return clinician


def _find_or_create_clinician(session: Session) -> Clinician:
    existing = session.execute(
        select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
    ).scalar_one_or_none()
    if existing is not None:
        # Backfill email if the row predates WALKTHROUGH_CLINICIAN_EMAIL being set.
        configured_email = get_settings().walkthrough_clinician_email
        if existing.email is None and configured_email:
            existing.email = configured_email
        return existing

    clinician = Clinician(
        name=WALKTHROUGH_CLINICIAN_NAME,
        specialty="General Practice",
        consent_status="granted",
        # Lets her first Google login (api/google_auth.py) claim this row by
        # email instead of creating an unrelated, case-less one. Blank until
        # WALKTHROUGH_CLINICIAN_EMAIL is set in .env.
        email=get_settings().walkthrough_clinician_email or None,
    )
    session.add(clinician)
    session.flush()
    return clinician


def _case_from_record(clinician_id, raw: dict) -> Case:
    disposition = FROM_WALKTHROUGH_LABEL[raw["disposition"]]
    return Case(
        clinician_id=clinician_id,
        external_case_ref=raw.get("case_id"),
        transcript_or_summary=raw["case_text"],
        doctor_disposition=disposition.value,
        doctor_reasoning_notes=raw.get("disposition_reason"),
        source_type=SourceType.WALKTHROUGH,
        used_for_training=True,
        initial_impression=raw.get("initial_impression"),
        questions_to_ask=raw.get("questions_to_ask"),
        examination_or_checks=raw.get("examination_or_checks"),
        factors_toward_referral=raw.get("factors_toward_referral"),
        factors_against_referral=raw.get("factors_against_referral"),
        flip_up=raw.get("flip_up"),
        flip_down=raw.get("flip_down"),
        red_flags=raw.get("red_flags"),
        confidence_notes=raw.get("confidence"),
        general_rule=raw.get("general_rule"),
    )


def import_walkthrough_cases(
    path: Path = DEFAULT_JSON_PATH,
    session: Session | None = None,
    clinician_id: uuid.UUID | None = None,
) -> list[Case]:
    """`clinician_id` imports for that specific, already-existing clinician
    (the self-service upload path, Phase K). Omit it only for the pilot
    doctor's own scripts/tests, which still resolve her by the legacy
    name/email constants."""
    owns_session = session is None
    session = session or SessionLocal()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        clinician = (
            _get_clinician(session, clinician_id)
            if clinician_id is not None
            else _find_or_create_clinician(session)
        )

        # Precedent vectors FK-reference cases, so they must go first -- a re-run after
        # embed_walkthrough_cases.py has populated them would otherwise hit a FK violation.
        session.execute(
            delete(CasePrecedentVector).where(
                CasePrecedentVector.clinician_id == clinician.clinician_id
            )
        )
        session.execute(delete(Case).where(Case.clinician_id == clinician.clinician_id))

        cases = [_case_from_record(clinician.clinician_id, raw) for raw in data["cases"]]
        session.add_all(cases)
        session.commit()
        return cases
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    imported = import_walkthrough_cases()
    print(f"Imported {len(imported)} walkthrough cases.")
