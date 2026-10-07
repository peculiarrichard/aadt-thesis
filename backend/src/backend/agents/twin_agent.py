"""Layer 7 configurable agent (Section 5.7): one entry point covering the four
ablation configurations from Section 10 -- guideline only, guideline+precedent,
guideline+persona, and the full system. Across every configuration, guideline
evidence, the constraint checker, and the explanation step are always computed,
and the constraint checker's veto always applies (Section 9: required in every
mode). This is the "full twin" (precedent + persona + guideline) that Section 10's
central experiment compares against the guideline-only baseline.

Operational definition of the two "partial" ablations, since the design doc lists
them but doesn't spell out how "precedent" and "persona" decouple when persona is
itself defined as retrieval-based conditioning: guideline+precedent retrieves the
k nearest cases and surfaces them as cited evidence, drafting via a deterministic
case-based-reasoning vote (no LLM call); guideline+persona calls the LLM for
few-shot conditioning without retrieval feeding it. The full system is precedent
retrieval feeding the LLM few-shot call.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.agents.explanation import Explanation, build_explanation
from backend.agents.guideline_grounding import retrieve_guideline_evidence
from backend.agents.persona_agent import PersonaParseError, draft_from_persona
from backend.agents.precedent_retrieval import DEFAULT_K, retrieve_precedent_cases
from backend.config import get_settings
from backend.constraints.checker import ConstraintCheckResult, check_constraints
from backend.db.models import Case
from backend.disposition import DISPOSITION_SEVERITY_ORDER, DispositionClass

_NO_EVIDENCE_CONFIDENCE = 0.35
_EVIDENCE_FOUND_CONFIDENCE = 0.8
_PERSONA_CONFIDENCE = 0.7
_CONSTRAINT_VIOLATION_CONFIDENCE_CAP = 0.2
_PERSONA_PARSE_FAILURE_CONFIDENCE = 0.0

_LEAST_SEVERE = DISPOSITION_SEVERITY_ORDER[0]


@dataclass(frozen=True)
class AgentConfig:
    use_precedent: bool
    use_persona: bool

    @property
    def label(self) -> str:
        if self.use_precedent and self.use_persona:
            return "full_system"
        if self.use_persona:
            return "guideline_plus_persona"
        if self.use_precedent:
            return "guideline_plus_precedent"
        return "guideline_only"


GUIDELINE_ONLY = AgentConfig(use_precedent=False, use_persona=False)
GUIDELINE_PLUS_PRECEDENT = AgentConfig(use_precedent=True, use_persona=False)
GUIDELINE_PLUS_PERSONA = AgentConfig(use_precedent=False, use_persona=True)
FULL_SYSTEM = AgentConfig(use_precedent=True, use_persona=True)
ALL_CONFIGS = (GUIDELINE_ONLY, GUIDELINE_PLUS_PRECEDENT, GUIDELINE_PLUS_PERSONA, FULL_SYSTEM)


@dataclass(frozen=True)
class AgentOutput:
    config_label: str
    draft_disposition: DispositionClass
    disposition: DispositionClass
    confidence: float
    escalated: bool
    escalation_reasons: list[str]
    constraint_check: ConstraintCheckResult
    explanation: Explanation
    precedent_case_refs: list[str] = field(default_factory=list)


def _most_severe(violations) -> DispositionClass:
    return max((v.minimum_disposition for v in violations), key=DISPOSITION_SEVERITY_ORDER.index)


def _majority_disposition(cases: list[Case]) -> DispositionClass:
    """Case-based-reasoning vote among retrieved precedent cases' actual
    dispositions. Ties broken toward the more severe class -- same "don't
    under-triage" bias as the constraint checker."""
    counts: dict[DispositionClass, int] = {}
    for case in cases:
        disposition = DispositionClass(case.doctor_disposition)
        counts[disposition] = counts.get(disposition, 0) + 1
    best_count = max(counts.values())
    tied = [disposition for disposition, count in counts.items() if count == best_count]
    return max(tied, key=DISPOSITION_SEVERITY_ORDER.index)


def run_twin_agent(
    session: Session,
    clinician_id: uuid.UUID,
    case_text: str,
    config: AgentConfig,
    exclude_case_id: uuid.UUID | None = None,
    confidence_threshold: float | None = None,
    precedent_k: int = DEFAULT_K,
) -> AgentOutput:
    """perceive -> retrieve (guideline always; precedent if configured) -> draft ->
    check -> explain -> escalate."""
    perceived_text = case_text.strip()
    matches = retrieve_guideline_evidence(session, perceived_text)

    precedent_cases: list[Case] = []
    if config.use_precedent or config.use_persona:
        from backend.ingestion.embeddings import embed_texts  # deferred: heavy (BGE-M3/torch)

        query_embedding = embed_texts([perceived_text])[0]
        precedent_cases = retrieve_precedent_cases(
            session,
            clinician_id,
            query_embedding,
            exclude_case_id=exclude_case_id,
            k=precedent_k,
        )

    draft = _LEAST_SEVERE
    reasoning_note: str | None = None
    persona_failed = False

    if config.use_persona and precedent_cases:
        try:
            persona_draft = draft_from_persona(perceived_text, precedent_cases)
            draft = persona_draft.disposition
            reasoning_note = persona_draft.reasoning
        except PersonaParseError:
            persona_failed = True
    elif config.use_precedent and precedent_cases:
        draft = _majority_disposition(precedent_cases)

    constraint_result = check_constraints(perceived_text, draft)

    if persona_failed:
        confidence = _PERSONA_PARSE_FAILURE_CONFIDENCE
    elif config.use_persona and precedent_cases:
        confidence = _PERSONA_CONFIDENCE
    elif matches:
        confidence = _EVIDENCE_FOUND_CONFIDENCE
    else:
        confidence = _NO_EVIDENCE_CONFIDENCE
    if not constraint_result.passed:
        confidence = min(confidence, _CONSTRAINT_VIOLATION_CONFIDENCE_CAP)

    disposition = draft
    reasons: list[str] = []
    if persona_failed:
        reasons.append("persona_response_unparseable")
    if not constraint_result.passed:
        disposition = _most_severe(constraint_result.violations)
        reasons.append("constraint_violation")

    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else get_settings().confidence_threshold
    )
    if confidence < threshold:
        reasons.append("low_confidence")

    explanation = build_explanation(matches, constraint_result)
    if reasoning_note:
        explanation = Explanation(
            matched_conditions=explanation.matched_conditions,
            guideline_evidence=explanation.guideline_evidence,
            constraint_rules_triggered=explanation.constraint_rules_triggered,
            reasoning_summary=f"{reasoning_note} {explanation.reasoning_summary}",
        )

    return AgentOutput(
        config_label=config.label,
        draft_disposition=draft,
        disposition=disposition,
        confidence=confidence,
        escalated=bool(reasons),
        escalation_reasons=reasons,
        constraint_check=constraint_result,
        explanation=explanation,
        precedent_case_refs=[
            case.external_case_ref or str(case.case_id) for case in precedent_cases
        ],
    )
