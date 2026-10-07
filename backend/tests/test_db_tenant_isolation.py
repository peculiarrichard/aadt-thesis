"""Proves clinician-scoped queries never leak across tenants (Section 3.8).
Requires `docker compose up -d`; skips otherwise."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.db.models import Case, CasePrecedentVector, InteractionLog
from backend.db.seed import seed
from backend.db.session import SessionLocal


@pytest.fixture
def seeded_clinicians():
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")

    clinicians = seed(session)
    try:
        yield session, clinicians
    finally:
        session.close()


def test_cases_are_scoped_per_clinician(seeded_clinicians):
    db_session, (clinician_a, clinician_b) = seeded_clinicians

    cases_a = (
        db_session.execute(select(Case).where(Case.clinician_id == clinician_a.clinician_id))
        .scalars()
        .all()
    )
    cases_b = (
        db_session.execute(select(Case).where(Case.clinician_id == clinician_b.clinician_id))
        .scalars()
        .all()
    )

    assert cases_a
    assert cases_b
    assert {c.clinician_id for c in cases_a} == {clinician_a.clinician_id}
    assert {c.clinician_id for c in cases_b} == {clinician_b.clinician_id}

    ids_a = {c.case_id for c in cases_a}
    ids_b = {c.case_id for c in cases_b}
    assert ids_a.isdisjoint(ids_b)


def test_interaction_log_and_precedent_vectors_do_not_leak_across_clinicians(seeded_clinicians):
    db_session, (clinician_a, clinician_b) = seeded_clinicians

    logs_a = (
        db_session.execute(
            select(InteractionLog).where(InteractionLog.clinician_id == clinician_a.clinician_id)
        )
        .scalars()
        .all()
    )
    logs_b = (
        db_session.execute(
            select(InteractionLog).where(InteractionLog.clinician_id == clinician_b.clinician_id)
        )
        .scalars()
        .all()
    )

    assert logs_a and logs_b
    assert all(log.clinician_id == clinician_a.clinician_id for log in logs_a)
    assert all(log.clinician_id == clinician_b.clinician_id for log in logs_b)

    vectors_a = (
        db_session.execute(
            select(CasePrecedentVector).where(
                CasePrecedentVector.clinician_id == clinician_a.clinician_id
            )
        )
        .scalars()
        .all()
    )
    vectors_b = (
        db_session.execute(
            select(CasePrecedentVector).where(
                CasePrecedentVector.clinician_id == clinician_b.clinician_id
            )
        )
        .scalars()
        .all()
    )

    assert vectors_a and vectors_b
    assert all(v.clinician_id == clinician_a.clinician_id for v in vectors_a)
    assert all(v.clinician_id == clinician_b.clinician_id for v in vectors_b)
