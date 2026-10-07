"""Integration tests for the four ablation configs (Section 10) against the real
DB and the real embedded walkthrough cases. Only the LLM call is mocked (no
live Ollama dependency for these) -- retrieval, the constraint checker, and the
case-based-reasoning vote are exercised for real. Requires `docker compose up -d`
plus a prior import+embed of the walkthrough cases; skips otherwise.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.agents.persona_agent import PersonaDraft, PersonaParseError
from backend.agents.twin_agent import (
    FULL_SYSTEM,
    GUIDELINE_ONLY,
    GUIDELINE_PLUS_PERSONA,
    GUIDELINE_PLUS_PRECEDENT,
    run_twin_agent,
)
from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
from backend.db.models import Case, Clinician
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass


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
        session.close()


def _held_out_case(session, external_ref: str) -> Case:
    return session.execute(select(Case).where(Case.external_case_ref == external_ref)).scalar_one()


def test_guideline_only_matches_baseline_style_output(db_session):
    session, clinician = db_session
    held_out = _held_out_case(session, "S2-C06")  # thunderclap headache -- emergency

    output = run_twin_agent(
        session,
        clinician.clinician_id,
        held_out.transcript_or_summary,
        GUIDELINE_ONLY,
        exclude_case_id=held_out.case_id,
    )

    assert output.config_label == "guideline_only"
    assert output.precedent_case_refs == []


def test_guideline_plus_precedent_uses_real_retrieval_no_llm_call(db_session):
    session, clinician = db_session
    held_out = _held_out_case(session, "S1-C02")  # malaria, scheduled_appointment

    with patch("backend.agents.twin_agent.draft_from_persona") as mocked_persona:
        output = run_twin_agent(
            session,
            clinician.clinician_id,
            held_out.transcript_or_summary,
            GUIDELINE_PLUS_PRECEDENT,
            exclude_case_id=held_out.case_id,
        )

    mocked_persona.assert_not_called()
    assert output.config_label == "guideline_plus_precedent"
    assert len(output.precedent_case_refs) > 0
    assert held_out.external_case_ref not in output.precedent_case_refs


def test_guideline_plus_persona_calls_the_llm_with_retrieved_examples(db_session):
    session, clinician = db_session
    held_out = _held_out_case(session, "S1-C02")

    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SCHEDULED_APPOINTMENT, reasoning="matches precedent"
        ),
    ) as mocked_persona:
        output = run_twin_agent(
            session,
            clinician.clinician_id,
            held_out.transcript_or_summary,
            GUIDELINE_PLUS_PERSONA,
            exclude_case_id=held_out.case_id,
        )

    mocked_persona.assert_called_once()
    assert output.draft_disposition == DispositionClass.SCHEDULED_APPOINTMENT
    assert "matches precedent" in output.explanation.reasoning_summary


def test_full_system_escalates_when_persona_response_is_unparseable(db_session):
    session, clinician = db_session
    held_out = _held_out_case(session, "S1-C02")

    with patch(
        "backend.agents.twin_agent.draft_from_persona", side_effect=PersonaParseError("bad")
    ):
        output = run_twin_agent(
            session,
            clinician.clinician_id,
            held_out.transcript_or_summary,
            FULL_SYSTEM,
            exclude_case_id=held_out.case_id,
        )

    assert output.escalated is True
    assert "persona_response_unparseable" in output.escalation_reasons
    assert output.confidence == 0.0


def test_constraint_checker_veto_overrides_an_under_triaged_persona_draft(db_session):
    session, clinician = db_session
    held_out = _held_out_case(session, "S1-C02")

    # BP 210/130 trips RF-005 (hypertensive-crisis threshold, a real, purely
    # numeric rule) regardless of what the (mocked) persona call says.
    with patch(
        "backend.agents.twin_agent.draft_from_persona",
        return_value=PersonaDraft(
            disposition=DispositionClass.SELF_CARE_ADVICE, reasoning="under-triaged on purpose"
        ),
    ):
        output = run_twin_agent(
            session,
            clinician.clinician_id,
            "Patient feels fine otherwise. Blood pressure 210/130 on repeat check.",
            FULL_SYSTEM,
            exclude_case_id=held_out.case_id,
        )

    assert output.draft_disposition == DispositionClass.SELF_CARE_ADVICE
    assert output.disposition == DispositionClass.URGENT_REFERRAL
    assert "constraint_violation" in output.escalation_reasons
    assert output.escalated is True
