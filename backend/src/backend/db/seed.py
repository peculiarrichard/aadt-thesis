"""Synthetic dummy data proving clinician tenant isolation (Section 3, point 8).

Not real clinician or patient data. Safe to run against a scratch dev database;
re-running clears and re-inserts everything below.

Deliberately does not touch guideline_documents/guideline_chunks/guideline_graph_*:
those are shared, not tenant-scoped, and owned by the ingestion pipeline
(backend/src/backend/ingestion/pipeline.py) — re-running this seed must not destroy
a real ingested guideline corpus.
"""

import datetime
import random
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.db.enums import AuditActor, ClinicianAction, ConsentSubjectType, Mode, SourceType
from backend.db.models import (
    AuditLog,
    CasePrecedentVector,
    Clinician,
    ConsentRegistry,
    Consultation,
    InteractionLog,
)
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass

_RNG_SEED = 42
_SEEDED_TABLES_CHILD_TO_PARENT = (
    AuditLog,
    InteractionLog,
    CasePrecedentVector,
    ConsentRegistry,
    Consultation,
    Clinician,
)


def _random_embedding(rng: random.Random, dim: int = 1024) -> list[float]:
    return [rng.uniform(-1, 1) for _ in range(dim)]


def _clear_existing(session: Session) -> None:
    for model in _SEEDED_TABLES_CHILD_TO_PARENT:
        session.execute(delete(model))


def seed(session: Session | None = None) -> None:
    owns_session = session is None
    session = session or SessionLocal()
    rng = random.Random(_RNG_SEED)
    try:
        _clear_existing(session)

        clinicians = [
            Clinician(
                name="Dr. Amaka Synthetic",
                specialty="Family Medicine",
                credentials="MBBS (synthetic dev fixture)",
                consent_status="granted",
                consent_date=datetime.datetime.now(datetime.UTC),
            ),
            Clinician(
                name="Dr. Bello Synthetic",
                specialty="Internal Medicine",
                credentials="MBBS (synthetic dev fixture)",
                consent_status="pending",
            ),
        ]
        session.add_all(clinicians)
        session.flush()

        for clinician in clinicians:
            consultations = [
                Consultation(
                    clinician_id=clinician.clinician_id,
                    patient_ref=f"synthetic-patient-{uuid.uuid4().hex[:8]}",
                    transcript_or_summary="Synthetic case for dev/testing only.",
                    doctor_disposition=rng.choice(list(DispositionClass)),
                    source_type=rng.choice(list(SourceType)),
                    used_for_training=True,
                )
                for _ in range(2)
            ]
            session.add_all(consultations)
            session.flush()

            for consultation in consultations:
                session.add(
                    CasePrecedentVector(
                        clinician_id=clinician.clinician_id,
                        consultation_id=consultation.consultation_id,
                        embedding=_random_embedding(rng),
                    )
                )
                session.add(
                    InteractionLog(
                        clinician_id=clinician.clinician_id,
                        mode=Mode.CONSULTING_SANDBOX,
                        input_case_ref=str(consultation.consultation_id),
                        draft_disposition=consultation.doctor_disposition,
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
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    seed()
    print("Seed complete.")
