"""Verifies the real walkthrough-case import (Section 6.1's sole clinician-specific
dataset). Requires `docker compose up -d`; skips otherwise. Deliberately does not
clean up after itself: this is real data other work (the LOOCV harness) depends on,
the same way db/seed.py's dummy data persists for other tests to build on.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME, import_walkthrough_cases
from backend.db.models import Case, Clinician
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass


@pytest.fixture
def require_db() -> None:
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")
    session.close()


@pytest.fixture(autouse=True, scope="module")
def _restore_precedent_vectors():
    """import_walkthrough_cases() deletes case_precedent_vectors as a side effect
    (FK to cases), so this module's real re-import runs would silently strand
    other tests/the LOOCV harness without embeddings. Re-embed once after this
    module's tests finish, mirroring the real setup sequence (import, then embed)."""
    yield
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        return
    session.close()

    from backend.db.embed_walkthrough_cases import embed_walkthrough_cases

    embed_walkthrough_cases()


def test_imports_all_cases_for_one_clinician(require_db: None):
    del require_db
    cases = import_walkthrough_cases()

    assert len(cases) == 34
    assert len({case.clinician_id for case in cases}) == 1


def test_disposition_distribution_matches_the_source_data(require_db: None):
    del require_db
    cases = import_walkthrough_cases()

    counts = {disposition: 0 for disposition in DispositionClass}
    for case in cases:
        counts[DispositionClass(case.doctor_disposition)] += 1

    assert counts[DispositionClass.SELF_CARE_ADVICE] == 3
    assert counts[DispositionClass.SCHEDULED_APPOINTMENT] == 7
    assert counts[DispositionClass.URGENT_REFERRAL] == 24


def test_external_case_ref_is_populated(require_db: None):
    del require_db
    cases = import_walkthrough_cases()

    refs = {case.external_case_ref for case in cases}
    assert "S1-C02" in refs
    assert None not in refs


def test_rerun_is_idempotent_not_duplicated(require_db: None):
    del require_db
    import_walkthrough_cases()
    import_walkthrough_cases()

    session = SessionLocal()
    clinician = session.execute(
        select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
    ).scalar_one()
    case_count = len(
        session.execute(select(Case).where(Case.clinician_id == clinician.clinician_id))
        .scalars()
        .all()
    )
    clinician_count = len(
        session.execute(select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME))
        .scalars()
        .all()
    )
    session.close()

    assert case_count == 34
    assert clinician_count == 1
