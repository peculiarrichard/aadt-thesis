"""Real end-to-end smoke test for the LOOCV harness (Section 10): runs every
case x 4 configs against a live Ollama and the real DB. Skipped by default
(slow: 4x as many real LLM calls as there are cases) -- run explicitly with
`RUN_LOOCV_SMOKE_TEST=1 uv run pytest tests/test_loocv_smoke.py` once Ollama is
running and the walkthrough cases are imported+embedded.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOOCV_SMOKE_TEST") != "1",
    reason="runs real LLM calls against live Ollama; set RUN_LOOCV_SMOKE_TEST=1 to run",
)


def test_loocv_runs_end_to_end_and_writes_one_row_per_case_per_config():
    from sqlalchemy import select

    from backend.agents.twin_agent import ALL_CONFIGS
    from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
    from backend.db.models import Case, Clinician, InteractionLog
    from backend.db.session import SessionLocal
    from backend.evaluation.loocv import run_loocv

    session = SessionLocal()
    clinician = session.execute(
        select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
    ).scalar_one()
    case_count = len(
        session.execute(select(Case).where(Case.clinician_id == clinician.clinician_id))
        .scalars()
        .all()
    )
    session.close()

    results = run_loocv()

    assert set(results.keys()) == {config.label for config in ALL_CONFIGS}
    for summary in results.values():
        assert summary.n == case_count

    session = SessionLocal()
    logged = (
        session.execute(
            select(InteractionLog).where(InteractionLog.clinician_id == clinician.clinician_id)
        )
        .scalars()
        .all()
    )
    session.close()

    assert len(logged) == case_count * len(ALL_CONFIGS)
