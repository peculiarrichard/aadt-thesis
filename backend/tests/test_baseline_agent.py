"""Unit tests (no DB) plus DB-backed integration tests against the synthetic case
set (task 9). Requires `docker compose up -d`; skips otherwise."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.baseline_agent import compute_confidence, evaluate_case, run_baseline_agent
from backend.agents.guideline_grounding import GuidelineMatch
from backend.db.enums import GraphNodeType
from backend.db.models import GuidelineDocument, GuidelineGraphNode
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass
from backend.fixtures.loader import load_synthetic_cases

# --- pure evaluate_case / compute_confidence tests --------------------------

_MALARIA_MATCH = GuidelineMatch(
    condition="MALARIA", symptoms=["Fever"], recommendations=["ACT"], document_source="nigeria_stg"
)


def test_confidence_is_higher_with_guideline_evidence():
    from backend.constraints.checker import ConstraintCheckResult

    passed = ConstraintCheckResult(passed=True, violations=[])
    assert compute_confidence([_MALARIA_MATCH], passed) > compute_confidence([], passed)


def test_confidence_is_capped_low_on_constraint_violation():
    from backend.constraints.checker import ConstraintCheckResult, ConstraintViolation

    violated = ConstraintCheckResult(
        passed=False,
        violations=[
            ConstraintViolation(
                rule_id="RF-001",
                description="x",
                minimum_disposition=DispositionClass.REFER_URGENT_EMERGENCY,
            )
        ],
    )
    assert compute_confidence([_MALARIA_MATCH], violated) <= 0.2


def test_baseline_draft_is_always_the_least_severe_class_when_no_red_flag():
    result = evaluate_case("patient with mild seasonal cold symptoms", [], confidence_threshold=0.0)

    assert result.draft_disposition == DispositionClass.MANAGE_AT_PRIMARY_CARE
    assert result.disposition == DispositionClass.MANAGE_AT_PRIMARY_CARE
    assert result.constraint_check.passed


def test_red_flag_escalates_disposition_and_sets_reason():
    text = "Crushing central chest pain; ECG shows ST-segment elevation."
    result = evaluate_case(text, [], confidence_threshold=0.0)

    assert result.disposition == DispositionClass.REFER_URGENT_EMERGENCY
    assert "constraint_violation" in result.escalation_reasons
    assert result.escalated


def test_low_confidence_escalates_even_without_a_red_flag():
    result = evaluate_case("vague complaint with no guideline match", [], confidence_threshold=0.9)

    assert result.escalated
    assert "low_confidence" in result.escalation_reasons
    assert result.constraint_check.passed


def test_sufficient_confidence_and_no_red_flag_does_not_escalate():
    result = evaluate_case(
        "routine follow-up, no danger signs", [_MALARIA_MATCH], confidence_threshold=0.5
    )

    assert not result.escalated
    assert result.escalation_reasons == []


def test_explanation_cites_matched_conditions():
    result = evaluate_case(
        "fever, RDT positive for malaria", [_MALARIA_MATCH], confidence_threshold=0.0
    )

    assert "MALARIA" in result.explanation.matched_conditions


# --- integration: full loop against the real synthetic case set -------------


@pytest.fixture
def seeded_graph_session():
    """Seeds real condition labels without depending on the full corpus ingest."""
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")

    document = GuidelineDocument(title="Baseline Agent Test Fixture", source="test-fixture")
    session.add(document)
    session.flush()

    labels = {
        case.related_guideline_conditions[0]
        for case in load_synthetic_cases()
        if case.related_guideline_conditions
    }
    nodes = [
        GuidelineGraphNode(
            document_id=document.document_id, node_type=GraphNodeType.CONDITION, label=label
        )
        for label in labels
    ]
    session.add_all(nodes)
    session.commit()

    try:
        yield session
    finally:
        session.execute(
            delete(GuidelineGraphNode).where(GuidelineGraphNode.document_id == document.document_id)
        )
        session.execute(
            delete(GuidelineDocument).where(GuidelineDocument.document_id == document.document_id)
        )
        session.commit()
        session.close()


def test_emergency_synthetic_cases_escalate_via_baseline_agent(seeded_graph_session):
    emergency_cases = [
        case
        for case in load_synthetic_cases()
        if case.doctor_disposition == DispositionClass.REFER_URGENT_EMERGENCY
    ]
    assert len(emergency_cases) == 5

    for case in emergency_cases:
        output = run_baseline_agent(
            seeded_graph_session,
            case.presenting_complaint,
            case.history,
            case.examination_findings,
        )
        assert output.escalated, f"{case.case_id} should have escalated"
        assert output.disposition == DispositionClass.REFER_URGENT_EMERGENCY


def test_baseline_agent_runs_without_error_on_every_synthetic_case(seeded_graph_session):
    for case in load_synthetic_cases():
        output = run_baseline_agent(
            seeded_graph_session,
            case.presenting_complaint,
            case.history,
            case.examination_findings,
        )
        assert output.confidence >= 0.0
        assert output.explanation.reasoning_summary
