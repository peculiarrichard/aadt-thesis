"""Layer 5 explainable AI (Section 5.5). Baseline agent only, so no
persona/precedent citations yet -- see docs/build_log.md task 9."""

from dataclasses import dataclass

from backend.agents.guideline_grounding import GuidelineMatch
from backend.constraints.checker import ConstraintCheckResult

_MAX_EVIDENCE_LINES = 6


@dataclass(frozen=True)
class Explanation:
    matched_conditions: list[str]
    guideline_evidence: list[str]
    constraint_rules_triggered: list[str]
    reasoning_summary: str


def build_explanation(
    matches: list[GuidelineMatch], constraint_result: ConstraintCheckResult
) -> Explanation:
    matched_conditions = [match.condition for match in matches]

    evidence: list[str] = []
    for match in matches:
        evidence.extend(f"{match.condition}: {symptom}" for symptom in match.symptoms)
        evidence.extend(
            f"{match.condition}: {recommendation}" for recommendation in match.recommendations
        )
    evidence = evidence[:_MAX_EVIDENCE_LINES]

    rule_ids = [violation.rule_id for violation in constraint_result.violations]

    if rule_ids:
        summary = (
            f"Escalated: case text tripped red flag rule(s) {', '.join(rule_ids)} from the "
            "constraint checker."
        )
    elif matched_conditions:
        summary = f"Guideline evidence found for: {', '.join(matched_conditions)}."
    else:
        summary = (
            "No matching guideline condition found in the corpus for this case; "
            "baseline draft has low confidence."
        )

    return Explanation(
        matched_conditions=matched_conditions,
        guideline_evidence=evidence,
        constraint_rules_triggered=rule_ids,
        reasoning_summary=summary,
    )
