"""Synthetic dummy data for tenant isolation testing (Section 3.8). Not real
clinician/patient data. Does not touch guideline_* tables (shared, not
tenant-scoped, owned by ingestion/pipeline.py) -- re-running this must not
destroy a real ingested corpus.

Scoped to its own two named clinicians only (SYNTHETIC_CLINICIAN_NAMES), not a
blanket delete of every table: a real clinician's imported data (see
db/import_walkthrough_cases.py) now coexists in the same database and must
survive a re-run of this seed script.
"""

import datetime
import random

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.db.enums import AuditActor, ClinicianAction, ConsentSubjectType, Mode, SourceType
from backend.db.models import (
    AuditLog,
    Case,
    CasePrecedentVector,
    Clinician,
    ConsentRegistry,
    InteractionLog,
)
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass

_RNG_SEED = 42
# Public: tests use this to identify seed.py's own clinicians rather than assuming
# they're the only ones in the database (a real clinician's data now coexists here).
SYNTHETIC_CLINICIAN_NAMES = ("Dr. Amaka Synthetic", "Dr. Bello Synthetic")
_CLINICIAN_SCOPED_TABLES_CHILD_TO_PARENT = (
    AuditLog,
    InteractionLog,
    CasePrecedentVector,
    ConsentRegistry,
    Case,
)


def _random_embedding(rng: random.Random, dim: int = 1024) -> list[float]:
    return [rng.uniform(-1, 1) for _ in range(dim)]


def _clear_existing(session: Session) -> None:
    existing_ids = (
        session.execute(
            select(Clinician.clinician_id).where(Clinician.name.in_(SYNTHETIC_CLINICIAN_NAMES))
        )
        .scalars()
        .all()
    )
    if not existing_ids:
        return
    for model in _CLINICIAN_SCOPED_TABLES_CHILD_TO_PARENT:
        session.execute(delete(model).where(model.clinician_id.in_(existing_ids)))
    session.execute(delete(Clinician).where(Clinician.clinician_id.in_(existing_ids)))


def seed(session: Session | None = None) -> list[Clinician]:
    owns_session = session is None
    session = session or SessionLocal()
    rng = random.Random(_RNG_SEED)
    try:
        _clear_existing(session)

        clinicians = [
            Clinician(
                name=SYNTHETIC_CLINICIAN_NAMES[0],
                specialty="Family Medicine",
                credentials="MBBS (synthetic dev fixture)",
                consent_status="granted",
                consent_date=datetime.datetime.now(datetime.UTC),
            ),
            Clinician(
                name=SYNTHETIC_CLINICIAN_NAMES[1],
                specialty="Internal Medicine",
                credentials="MBBS (synthetic dev fixture)",
                consent_status="pending",
            ),
        ]
        session.add_all(clinicians)
        session.flush()

        for clinician in clinicians:
            cases = [
                Case(
                    clinician_id=clinician.clinician_id,
                    transcript_or_summary="Synthetic case for dev/testing only.",
                    doctor_disposition=rng.choice(list(DispositionClass)),
                    source_type=rng.choice(list(SourceType)),
                    used_for_training=True,
                )
                for _ in range(2)
            ]
            session.add_all(cases)
            session.flush()

            for case in cases:
                session.add(
                    CasePrecedentVector(
                        clinician_id=clinician.clinician_id,
                        case_id=case.case_id,
                        embedding=_random_embedding(rng),
                    )
                )
                session.add(
                    InteractionLog(
                        clinician_id=clinician.clinician_id,
                        mode=Mode.CONSULTING_SANDBOX,
                        input_case_ref=str(case.case_id),
                        draft_disposition=case.doctor_disposition,
                        confidence_score=rng.uniform(0.5, 0.99),
                        clinician_action=ClinicianAction.APPROVED,
                    )
                )

            session.add(
                ConsentRegistry(
                    clinician_id=clinician.clinician_id,
                    subject_type=ConsentSubjectType.CLINICIAN,
                    scope="dev-seed",
                    granted_at=datetime.datetime.now(datetime.UTC),
                )
            )
            session.add(
                AuditLog(
                    clinician_id=clinician.clinician_id,
                    actor=AuditActor.SYSTEM,
                    action="seed_dummy_data",
                    reference_table="clinicians",
                    reference_id=str(clinician.clinician_id),
                )
            )

        session.commit()
        return clinicians
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    seed()
    print("Seed complete.")
