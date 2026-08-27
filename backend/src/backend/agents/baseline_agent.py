"""Layer 7 guideline-only baseline agent (Section 5.7, build_plan.md task 9).
Draft/check design and confidence formula: docs/build_log.md task 9."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.agents.explanation import Explanation, build_explanation
from backend.agents.guideline_grounding import GuidelineMatch, retrieve_guideline_evidence
from backend.agents.perceive import perceive
from backend.config import get_settings
from backend.constraints.checker import ConstraintCheckResult, check_constraints
from backend.disposition import DISPOSITION_SEVERITY_ORDER, DispositionClass

_NO_EVIDENCE_CONFIDENCE = 0.35
_EVIDENCE_FOUND_CONFIDENCE = 0.8
_CONSTRAINT_VIOLATION_CONFIDENCE_CAP = 0.2

_BASELINE_DRAFT = DISPOSITION_SEVERITY_ORDER[0]


@dataclass(frozen=True)
class AgentOutput:
    draft_disposition: DispositionClass
    disposition: DispositionClass
    confidence: float
    escalated: bool
    escalation_reasons: list[str]
    constraint_check: ConstraintCheckResult
    explanation: Explanation


def compute_confidence(
    matches: list[GuidelineMatch], constraint_result: ConstraintCheckResult
) -> float:
    confidence = _EVIDENCE_FOUND_CONFIDENCE if matches else _NO_EVIDENCE_CONFIDENCE
    if not constraint_result.passed:
        confidence = min(confidence, _CONSTRAINT_VIOLATION_CONFIDENCE_CAP)
    return confidence


def _most_severe(violations) -> DispositionClass:
    return max(
        (v.minimum_disposition for v in violations),
        key=DISPOSITION_SEVERITY_ORDER.index,
    )


def evaluate_case(
    case_text: str,
    matches: list[GuidelineMatch],
    confidence_threshold: float,
) -> AgentOutput:
    """draft -> check -> explain -> escalate; no DB access, unit-testable directly."""
    constraint_result = check_constraints(case_text, _BASELINE_DRAFT)
    confidence = compute_confidence(matches, constraint_result)

    disposition = _BASELINE_DRAFT
    reasons: list[str] = []

    if not constraint_result.passed:
        disposition = _most_severe(constraint_result.violations)
        reasons.append("constraint_violation")
    if confidence < confidence_threshold:
        reasons.append("low_confidence")

    explanation = build_explanation(matches, constraint_result)

    return AgentOutput(
        draft_disposition=_BASELINE_DRAFT,
        disposition=disposition,
        confidence=confidence,
        escalated=bool(reasons),
        escalation_reasons=reasons,
        constraint_check=constraint_result,
        explanation=explanation,
    )


def run_baseline_agent(
    session: Session,
    presenting_complaint: str,
    history: str,
    examination_findings: str,
    confidence_threshold: float | None = None,
) -> AgentOutput:
    """The full loop: perceive -> retrieve (DB) -> draft -> check -> explain ->
    escalate."""
    perceived = perceive(presenting_complaint, history, examination_findings)
    matches = retrieve_guideline_evidence(session, perceived.case_text)
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else get_settings().confidence_threshold
    )
    return evaluate_case(perceived.case_text, matches, threshold)
