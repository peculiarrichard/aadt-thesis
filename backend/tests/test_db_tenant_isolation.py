"""Proves clinician-scoped queries never leak across tenants (Section 3.8).
Requires `docker compose up -d`; skips otherwise."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.db.models import CasePrecedentVector, Clinician, Consultation, InteractionLog
from backend.db.seed import seed
from backend.db.session import SessionLocal


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")

    seed(session)
    try:
        yield session
    finally:
        session.close()


def test_consultations_are_scoped_per_clinician(db_session):
    clinician_a, clinician_b = db_session.execute(select(Clinician)).scalars().all()

    consultations_a = (
        db_session.execute(
            select(Consultation).where(Consultation.clinician_id == clinician_a.clinician_id)
        )
        .scalars()
        .all()
    )
    consultations_b = (
        db_session.execute(
            select(Consultation).where(Consultation.clinician_id == clinician_b.clinician_id)
        )
        .scalars()
        .all()
    )

    assert consultations_a
    assert consultations_b
    assert {c.clinician_id for c in consultations_a} == {clinician_a.clinician_id}
    assert {c.clinician_id for c in consultations_b} == {clinician_b.clinician_id}

    ids_a = {c.consultation_id for c in consultations_a}
    ids_b = {c.consultation_id for c in consultations_b}
    assert ids_a.isdisjoint(ids_b)


def test_interaction_log_and_precedent_vectors_do_not_leak_across_clinicians(db_session):
    clinician_a, clinician_b = db_session.execute(select(Clinician)).scalars().all()

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
