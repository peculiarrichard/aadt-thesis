"""Embeds a clinician's cases into case_precedent_vectors (Section 5.4's
precedent memory). Separate from import_walkthrough_cases.py because this needs
BGE-M3 (heavy import, deferred inside the function body so it doesn't slow
down every `pytest` run).

Generic per clinician (Phase I) -- pass `clinician_id` for any doctor; omitted,
falls back to the pilot doctor's legacy WALKTHROUGH_CLINICIAN_NAME lookup.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
from backend.db.models import Case, CasePrecedentVector, Clinician
from backend.db.session import SessionLocal


def _embedding_text(case: Case) -> str:
    parts = [case.transcript_or_summary, case.initial_impression, case.doctor_reasoning_notes]
    return " ".join(part for part in parts if part)


def embed_walkthrough_cases(
    session: Session | None = None, clinician_id: uuid.UUID | None = None
) -> int:
    from backend.ingestion.embeddings import embed_texts  # deferred: heavy (BGE-M3/torch)

    owns_session = session is None
    session = session or SessionLocal()
    try:
        if clinician_id is not None:
            resolved_id = clinician_id
        else:
            clinician = session.execute(
                select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
            ).scalar_one()
            resolved_id = clinician.clinician_id

        cases = list(
            session.execute(select(Case).where(Case.clinician_id == resolved_id)).scalars().all()
        )

        session.execute(
            delete(CasePrecedentVector).where(CasePrecedentVector.clinician_id == resolved_id)
        )

        texts = [_embedding_text(case) for case in cases]
        vectors = embed_texts(texts)

        for case, vector in zip(cases, vectors, strict=True):
            session.add(
                CasePrecedentVector(
                    clinician_id=resolved_id,
                    case_id=case.case_id,
                    embedding=vector,
                )
            )

        session.commit()
        return len(cases)
    finally:
        if owns_session:
            session.close()


def embed_single_case(session: Session, clinician_id: uuid.UUID, case: Case) -> None:
    """Phase O: embeds exactly one case without touching the rest of the
    clinician's precedent memory -- used when a consult correction needs to
    be folded back in immediately, where a full embed_walkthrough_cases()
    delete-and-rebuild would be wasteful and would momentarily empty her
    precedent memory for every other in-flight request."""
    from backend.ingestion.embeddings import embed_texts  # deferred: heavy (BGE-M3/torch)

    vector = embed_texts([_embedding_text(case)])[0]
    session.add(
        CasePrecedentVector(clinician_id=clinician_id, case_id=case.case_id, embedding=vector)
    )
    session.commit()


if __name__ == "__main__":
    count = embed_walkthrough_cases()
    print(f"Embedded {count} walkthrough cases.")
