"""Integration test against the real embedded walkthrough cases. Requires
`docker compose up -d` and a prior `python -m backend.db.embed_walkthrough_cases`
run; skips otherwise.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.agents.precedent_retrieval import retrieve_precedent_cases
from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
from backend.db.models import Case, Clinician
from backend.db.session import SessionLocal


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")

    clinician = session.execute(
        select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
    ).scalar_one_or_none()
    if clinician is None:
        session.close()
        pytest.skip(
            "walkthrough cases not imported/embedded; run "
            "`python -m backend.db.import_walkthrough_cases` and "
            "`python -m backend.db.embed_walkthrough_cases` first"
        )

    try:
        yield session, clinician
    finally:
        session.close()


def _embedding_for(session, case_id):
    from backend.db.models import CasePrecedentVector

    return session.execute(
        select(CasePrecedentVector.embedding).where(CasePrecedentVector.case_id == case_id)
    ).scalar_one()


def test_retrieves_k_cases_ordered_by_similarity(db_session):
    session, clinician = db_session
    seizure_case = session.execute(
        select(Case).where(Case.external_case_ref == "S5-C12")
    ).scalar_one()
    query_embedding = _embedding_for(session, seizure_case.case_id)

    results = retrieve_precedent_cases(session, clinician.clinician_id, query_embedding, k=4)

    assert len(results) == 4
    # the case's own embedding should be its own nearest neighbour when not excluded
    assert results[0].case_id == seizure_case.case_id


def test_excludes_the_held_out_case(db_session):
    session, clinician = db_session
    seizure_case = session.execute(
        select(Case).where(Case.external_case_ref == "S5-C12")
    ).scalar_one()
    query_embedding = _embedding_for(session, seizure_case.case_id)

    results = retrieve_precedent_cases(
        session,
        clinician.clinician_id,
        query_embedding,
        exclude_case_id=seizure_case.case_id,
        k=4,
    )

    assert len(results) == 4
    assert seizure_case.case_id not in {case.case_id for case in results}


def test_never_returns_another_clinicians_cases(db_session):
    session, clinician = db_session
    any_case = session.execute(
        select(Case).where(Case.clinician_id == clinician.clinician_id).limit(1)
    ).scalar_one()
    query_embedding = _embedding_for(session, any_case.case_id)

    # k deliberately larger than the dataset so this retrieves everything --
    # `limit(k)` just returns fewer rows if k exceeds what's available, so this
    # doesn't need updating as the dataset grows.
    results = retrieve_precedent_cases(session, clinician.clinician_id, query_embedding, k=1000)

    assert all(case.clinician_id == clinician.clinician_id for case in results)
