"""Layer 4 precedent memory (Section 5.4): the vector index of the doctor's own
cases, queried at inference time for the most similar precedent. Under leave-one-out
evaluation, the held-out case is excluded from this index for that fold.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Case, CasePrecedentVector

DEFAULT_K = 4


def retrieve_precedent_cases(
    session: Session,
    clinician_id: uuid.UUID,
    query_embedding: list[float],
    exclude_case_id: uuid.UUID | None = None,
    k: int = DEFAULT_K,
) -> list[Case]:
    query = (
        select(Case)
        .join(CasePrecedentVector, CasePrecedentVector.case_id == Case.case_id)
        .where(CasePrecedentVector.clinician_id == clinician_id)
    )
    if exclude_case_id is not None:
        query = query.where(Case.case_id != exclude_case_id)
    query = query.order_by(CasePrecedentVector.embedding.cosine_distance(query_embedding)).limit(k)
    return list(session.execute(query).scalars().all())
