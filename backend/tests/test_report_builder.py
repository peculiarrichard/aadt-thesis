"""Unit tests for the deterministic doctor's-report assembly (no DB, no LLM --
AgentOutput is constructed directly)."""

from backend.agents.explanation import Explanation
from backend.agents.report_builder import ClericalDetails, build_doctor_report
from backend.agents.twin_agent import AgentOutput
from backend.constraints.checker import ConstraintCheckResult
from backend.disposition import DispositionClass

_NO_CLERICAL = ClericalDetails()


def _make_output(
    disposition: DispositionClass,
    escalated: bool,
    escalation_reasons: list[str],
    reasoning_summary: str,
    guideline_evidence: list[str] | None = None,
) -> AgentOutput:
    return AgentOutput(
        config_label="full_system",
        draft_disposition=disposition,
        disposition=disposition,
        confidence=0.7,
        escalated=escalated,
        escalation_reasons=escalation_reasons,
        constraint_check=ConstraintCheckResult(passed=not escalated, violations=[]),
        explanation=Explanation(
            matched_conditions=[],
            guideline_evidence=guideline_evidence or [],
            constraint_rules_triggered=[],
            reasoning_summary=reasoning_summary,
        ),
        precedent_case_refs=["S1-C01", "S1-C02"],
    )


def test_report_shows_disposition_and_plan_when_not_escalated():
    output = _make_output(
        DispositionClass.SELF_CARE_ADVICE,
        escalated=False,
        escalation_reasons=[],
        reasoning_summary=(
            "She'd want to know how long the fever has lasted and whether there's "
            "any rash. No matching guideline condition found in the corpus for "
            "this case; baseline draft has low confidence."
        ),
    )

    report = build_doctor_report("Dr. Test", "fever for two days", _NO_CLERICAL, output)

    assert "self care advice" in report.assessment
    assert "70%" in report.assessment
    assert "Advise self-care at home" in report.plan
    assert "No matching guideline condition" not in report.history_and_impression
    assert "how long the fever has lasted" in report.history_and_impression


def test_report_withholds_disposition_when_escalated():
    output = _make_output(
        DispositionClass.URGENT_REFERRAL,
        escalated=True,
        escalation_reasons=["constraint_violation"],
        reasoning_summary="Escalated: case text tripped red flag rule(s) chest_pain_stemi.",
    )

    report = build_doctor_report("Dr. Test", "crushing chest pain", _NO_CLERICAL, output)

    assert "Escalated for clinician review" in report.assessment
    assert "constraint_violation" in report.assessment
    assert "Pending clinician review" in report.plan


def test_report_falls_back_when_persona_produced_no_narrative():
    output = _make_output(
        DispositionClass.SCHEDULED_APPOINTMENT,
        escalated=False,
        escalation_reasons=[],
        reasoning_summary="Guideline evidence found for: Malaria.",
    )

    report = build_doctor_report("Dr. Test", "mild fever", _NO_CLERICAL, output)

    assert "could not produce a narrative assessment" in report.history_and_impression


def test_report_carries_clerical_details_through_unchanged():
    output = _make_output(
        DispositionClass.SELF_CARE_ADVICE,
        escalated=False,
        escalation_reasons=[],
        reasoning_summary="",
    )
    clerical = ClericalDetails(patient_reference="Patient A", age="34", sex="female")

    report = build_doctor_report("Dr. Test", "case text", clerical, output)

    assert report.clerical == clerical
