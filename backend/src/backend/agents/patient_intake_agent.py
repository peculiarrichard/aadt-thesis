"""Patient-facing conversational intake (further work, outside the thesis's
evaluated methodology -- simulated patients only). Interviews a simulated
patient the way the doctor would, grounded in her own precedent cases, then
hands off to the existing run_twin_agent once enough has been gathered.

Distinct from persona_agent.py, which drafts a disposition directly from a
finished case description -- this agent's only job, each turn, is deciding
what to ask next or that enough has been gathered. The doctor's own
questions_to_ask/examination_or_checks/red_flags on similar past cases are
woven in as grounding for her history-taking style, not posed to the patient
verbatim -- same convention persona_agent.py's _format_example already uses
for "doctor-side workup becomes prose, not a literal question."
"""

from dataclasses import dataclass

from backend.db.models import Case
from backend.llm.client import chat_completion

_SYSTEM_PROMPT = (
    "You are a doctor's digital twin taking a history from a patient in a live chat, "
    "in the style of this specific doctor's own real history-taking habits (shown "
    "below as examples from her past cases -- her own workup habits, not questions "
    "to put to THIS patient verbatim). Ask ONE clinically relevant question at a "
    "time: onset, duration, severity, associated symptoms, relevant past history, "
    "medications, allergies, and red-flag screening relevant to the presenting "
    "complaint. Never ask the patient a meta-question about what the doctor herself "
    "would ask or test for -- those describe the doctor's own workup, not something "
    "to put to a patient. Once you have enough to summarize the case for the twin's "
    "assessment, stop asking.\n\n"
    "Respond with EXACTLY one of these two forms, nothing else:\n"
    "QUESTION: <the single next question to ask the patient>\n"
    "READY_TO_SUMMARIZE: <a concise clinical case summary synthesizing everything "
    "the patient has said so far, written the way a case would be presented to a "
    "doctor, not addressed to the patient>"
)

_RETRY_NUDGE = (
    "Your previous response did not follow the required format. Respond again with "
    "EXACTLY one line: either 'QUESTION: <...>' or 'READY_TO_SUMMARIZE: <...>'. No "
    "other text."
)


class IntakeParseError(Exception):
    """Mirrors PersonaParseError (persona_agent.py): an unparseable response
    here should make the caller end the interview, not crash."""


@dataclass(frozen=True)
class IntakeTurn:
    question: str | None  # set when the agent wants to ask another question
    case_summary: str | None  # set when the agent is ready to summarize


def next_intake_turn(
    presenting_complaint: str,
    history: list[dict[str, str]],
    precedent_cases: list[Case],
) -> IntakeTurn:
    example_blocks = [
        block for block in (_format_example(case) for case in precedent_cases) if block
    ]
    grounding = (
        "This doctor's own history-taking habits on similar past cases:\n\n"
        + "\n---\n".join(example_blocks)
        + "\n\n---\n\n"
        if example_blocks
        else ""
    )
    transcript = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    user_prompt = (
        f"{grounding}Patient's presenting complaint: {presenting_complaint}\n\n"
        f"Conversation so far:\n{transcript or '(nothing yet)'}\n\n"
        "What's the next question, or are you ready to summarize?"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = chat_completion(messages)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    # One retry with a stricter format reminder, same parsing contract as persona_agent.py.
    messages.append({"role": "assistant", "content": raw})
    messages.append({"role": "user", "content": _RETRY_NUDGE})
    raw_retry = chat_completion(messages)
    parsed_retry = _try_parse(raw_retry)
    if parsed_retry is not None:
        return parsed_retry

    raise IntakeParseError(f"could not parse a question or summary; last response: {raw_retry!r}")


def _format_example(case: Case) -> str:
    workup_parts = []
    if case.questions_to_ask:
        workup_parts.append("she'd ask about " + "; ".join(case.questions_to_ask).rstrip("."))
    if case.examination_or_checks:
        workup_parts.append("check " + case.examination_or_checks.rstrip("."))
    if case.red_flags:
        workup_parts.append("watch for " + case.red_flags.rstrip("."))
    if not workup_parts:
        return ""
    return f"Case: {case.transcript_or_summary}\nHer habits: {'; '.join(workup_parts)}"


def _try_parse(raw: str) -> IntakeTurn | None:
    # Marker-based, not line-based -- same reasoning as persona_agent.py's
    # _try_parse: a multi-sentence summary can wrap across several physical
    # lines, and a per-line scan would silently drop part of it.
    upper_raw = raw.upper()
    question_idx = upper_raw.find("QUESTION:")
    summary_idx = upper_raw.find("READY_TO_SUMMARIZE:")

    if question_idx != -1 and (summary_idx == -1 or question_idx < summary_idx):
        end = summary_idx if summary_idx != -1 else len(raw)
        question = " ".join(raw[question_idx + len("QUESTION:") : end].split())
        return IntakeTurn(question=question, case_summary=None) if question else None

    if summary_idx != -1:
        summary = " ".join(raw[summary_idx + len("READY_TO_SUMMARIZE:") :].split())
        return IntakeTurn(question=None, case_summary=summary) if summary else None

    return None
