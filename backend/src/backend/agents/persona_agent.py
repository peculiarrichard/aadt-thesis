"""Layer 4 persona conditioning (Section 5.4): retrieval-augmented few-shot
prompting, not weight fine-tuning. The base model is shown several of the doctor's
own worked examples (retrieved precedent cases) and asked to decide a new case the
way she would. No weights change; the persona lives entirely in what's retrieved
and how the prompt is built.
"""

from dataclasses import dataclass

from backend.db.models import Case
from backend.disposition import FROM_WALKTHROUGH_LABEL, DispositionClass
from backend.llm.client import chat_completion

_SYSTEM_PROMPT = (
    "You are conditioning your answer on one specific doctor's own past decisions. "
    "You will be shown several of her real cases as worked examples: her "
    "presentation, her workup (first impression, what she'd ask and check, what "
    "would push her toward or away from referral, what would change her mind), her "
    "reasoning, and her disposition. Then you will be given a new case. Decide the "
    "disposition this SAME doctor would most likely give, based on how she reasoned "
    "in the examples -- not generic medical guidance.\n\n"
    "Respond with EXACTLY two lines, nothing else:\n"
    "DISPOSITION: <self-care advice|scheduled appointment|urgent referral>\n"
    "REASONING: <a natural paragraph, two to four sentences, in her voice, as if "
    "she is talking through the case out loud -- weaving in her first impression, "
    "what she'd want to ask or check, and what would change her mind where they're "
    "relevant to THIS case. Never use labels, headers, or bullet points for these -- "
    "write connected prose, the way she would actually talk, not a form.>"
)

_RETRY_NUDGE = (
    "Your previous response did not follow the required format. Respond again with "
    "EXACTLY two lines: 'DISPOSITION: <one of the three exact phrases>' then "
    "'REASONING: <...>'. No other text."
)


class PersonaParseError(Exception):
    """The LLM's response couldn't be parsed into a valid disposition, even after
    one retry. Callers should treat this as a reason to escalate (Section 9), not
    crash -- an unparseable model response is exactly the kind of low-confidence
    situation the escalation path exists for."""


@dataclass(frozen=True)
class PersonaDraft:
    disposition: DispositionClass
    reasoning: str


def draft_from_persona(case_text: str, precedent_cases: list[Case]) -> PersonaDraft:
    examples = "\n---\n".join(_format_example(case) for case in precedent_cases)
    user_prompt = (
        f"Worked examples from this doctor's own past cases:\n\n{examples}\n\n---\n\n"
        f"New case: {case_text}\n\nWhat is her disposition and reasoning?"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = chat_completion(messages)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    # One retry with a stricter format reminder, per the design's parsing contract.
    messages.append({"role": "assistant", "content": raw})
    messages.append({"role": "user", "content": _RETRY_NUDGE})
    raw_retry = chat_completion(messages)
    parsed_retry = _try_parse(raw_retry)
    if parsed_retry is not None:
        return parsed_retry

    raise PersonaParseError(
        f"could not parse a disposition after retry; last response: {raw_retry!r}"
    )


def _format_example(case: Case) -> str:
    workup_parts = []
    if case.initial_impression:
        workup_parts.append(case.initial_impression.rstrip("."))
    if case.questions_to_ask:
        workup_parts.append("she'd ask about " + "; ".join(case.questions_to_ask).rstrip("."))
    if case.examination_or_checks:
        workup_parts.append("check " + case.examination_or_checks.rstrip("."))
    if case.factors_toward_referral:
        workup_parts.append("would refer if " + case.factors_toward_referral.rstrip("."))
    if case.factors_against_referral:
        workup_parts.append(
            "would manage it herself if " + case.factors_against_referral.rstrip(".")
        )
    if case.flip_up:
        workup_parts.append("would escalate further if " + case.flip_up.rstrip("."))
    if case.flip_down:
        workup_parts.append("would step it down if " + case.flip_down.rstrip("."))
    workup = "; ".join(workup_parts) if workup_parts else "(not recorded)"

    return (
        f"Case: {case.transcript_or_summary}\n"
        f"Her workup: {workup}\n"
        f"Her reasoning: {case.doctor_reasoning_notes or '(not recorded)'}\n"
        f"Her disposition: {case.doctor_disposition}"
    )


def _try_parse(raw: str) -> PersonaDraft | None:
    disposition: DispositionClass | None = None
    reasoning = ""
    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("DISPOSITION:"):
            label = stripped.split(":", 1)[1].strip().lower()
            disposition = FROM_WALKTHROUGH_LABEL.get(label)
            if disposition is None:
                # Model sometimes answers with the enum's own snake_case value
                # (e.g. "scheduled_appointment") instead of the human phrase.
                try:
                    disposition = DispositionClass(label)
                except ValueError:
                    pass
        elif upper.startswith("REASONING:"):
            reasoning = stripped.split(":", 1)[1].strip()

    if disposition is None:
        return None
    return PersonaDraft(disposition=disposition, reasoning=reasoning)
