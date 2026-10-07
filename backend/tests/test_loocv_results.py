"""Covers a real bug found while wiring this up: interaction_log is append-only
(models.py's own docstring: "Never overwritten"), so a re-run of the LOOCV batch
leaves the previous run's rows sitting alongside the new ones. load_results_from_log
must read only the latest row per (config, case) pair, not average across every
run that ever happened. Requires `docker compose up -d` and imported walkthrough
cases; skips otherwise. Cleans up its own rows -- never touches a real config
label, so it can't interfere with a real `python -m backend.evaluation.loocv` run.
"""

import datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.db.enums import Mode
from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
from backend.db.models import Case, Clinician, InteractionLog
from backend.db.session import SessionLocal
from backend.evaluation.loocv import load_results_from_log

_FAKE_LABEL = "test_loocv_results_fake_config"


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
        pytest.skip("walkthrough cases not imported/embedded")

    try:
        yield session, clinician
    finally:
        session.execute(delete(InteractionLog).where(InteractionLog.model_version == _FAKE_LABEL))
        session.commit()
        session.close()


def test_uses_only_the_latest_row_per_config_and_case(db_session):
    session, clinician = db_session
    case = session.execute(
        select(Case).where(Case.clinician_id == clinician.clinician_id).limit(1)
    ).scalar_one()

    now = datetime.datetime.now(datetime.UTC)
    stale = InteractionLog(
        clinician_id=clinician.clinician_id,
        mode=Mode.CONSULTING_SANDBOX,
        input_case_ref=case.external_case_ref,
        final_disposition="urgent_referral",
        model_version=_FAKE_LABEL,
        created_at=now - datetime.timedelta(minutes=5),
    )
    fresh = InteractionLog(
        clinician_id=clinician.clinician_id,
        mode=Mode.CONSULTING_SANDBOX,
        input_case_ref=case.external_case_ref,
        final_disposition="self_care_advice",
        model_version=_FAKE_LABEL,
        created_at=now,
    )
    session.add_all([stale, fresh])
    session.commit()

    results = load_results_from_log(session, clinician.clinician_id)

    assert results[_FAKE_LABEL].n == 1
