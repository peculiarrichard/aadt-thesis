"""Phase L: the one genuinely new AI component this phase adds. Turns raw,
unstructured text (a transcript after Whisper, or pasted/uploaded de-identified
case text) into the same structured shape the original walkthrough JSON uses
-- shared by every path that doesn't already arrive pre-structured (Phase M's
two recording flows and its de-identified-text upload), so there is one
extraction implementation, not one per source.

Same pattern as persona_agent.py: one chat_completion call, a strict output
contract, one retry on malformed output, never auto-saved -- the caller always
shows this back to the doctor as an editable draft before anything is
persisted as a real Case row.
"""

import json
from dataclasses import dataclass

from backend.disposition import FROM_WALKTHROUGH_LABEL
from backend.llm.client import chat_completion

_SYSTEM_PROMPT = (
    "You turn a doctor's raw spoken or written case narration into a structured "
    "clinical case record. Read the text and extract exactly these fields. If a "
    "field genuinely isn't mentioned, use null (for text fields) or an empty list "
    "(for questions_to_ask) -- never invent content that wasn't said.\n\n"
    "Respond with ONLY a single JSON object, no other text, with exactly these keys:\n"
    '{"case_text": "<a clean summary of the presentation itself>", '
    '"initial_impression": "<string or null>", '
    '"questions_to_ask": ["<string>", ...], '
    '"examination_or_checks": "<string or null>", '
    '"factors_toward_referral": "<string or null>", '
    '"factors_against_referral": "<string or null>", '
    '"flip_up": "<string or null>", '
    '"flip_down": "<string or null>", '
    '"red_flags": "<string or null>", '
    '"confidence": "<string or null>", '
    '"general_rule": "<string or null>", '
    '"disposition": '
    '"<exactly one of: self-care advice | scheduled appointment | urgent referral>", '
    '"disposition_reason": "<string or null>"}'
)

_RETRY_NUDGE = (
    "Your previous response was not valid JSON matching the required schema. "
    "Respond again with ONLY the JSON object, no markdown fences, no other text."
)


class CaseStructuringParseError(Exception):
    """The LLM's response couldn't be parsed into the required schema, even
    after one retry. Callers should surface this to the doctor as "couldn't
    auto-structure this, fill it in yourself" rather than crash -- the raw
    text is never lost, only the extraction step failed."""


@dataclass(frozen=True)
class StructuredCaseDraft:
    case_text: str
    initial_impression: str | None
    questions_to_ask: list[str]
    examination_or_checks: str | None
    factors_toward_referral: str | None
    factors_against_referral: str | None
    flip_up: str | None
    flip_down: str | None
    red_flags: str | None
    confidence: str | None
    general_rule: str | None
    disposition: str | None  # the walkthrough label, e.g. "self-care advice" -- may be
    # None if the extraction couldn't determine one; the doctor fills it in herself.
    disposition_reason: str | None


def draft_structured_case(raw_text: str) -> StructuredCaseDraft:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]

    raw = chat_completion(messages)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    messages.append({"role": "assistant", "content": raw})
    messages.append({"role": "user", "content": _RETRY_NUDGE})
    raw_retry = chat_completion(messages)
    parsed_retry = _try_parse(raw_retry)
    if parsed_retry is not None:
        return parsed_retry

    raise CaseStructuringParseError(
        f"could not parse a structured case after retry; last response: {raw_retry!r}"
    )


def _try_parse(raw: str) -> StructuredCaseDraft | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or "case_text" not in data:
        return None

    disposition_label = data.get("disposition")
    if disposition_label is not None and disposition_label not in FROM_WALKTHROUGH_LABEL:
        disposition_label = None

    questions = data.get("questions_to_ask") or []
    if not isinstance(questions, list):
        questions = []

    return StructuredCaseDraft(
        case_text=str(data["case_text"]),
        initial_impression=data.get("initial_impression"),
        questions_to_ask=[str(q) for q in questions],
        examination_or_checks=data.get("examination_or_checks"),
        factors_toward_referral=data.get("factors_toward_referral"),
        factors_against_referral=data.get("factors_against_referral"),
        flip_up=data.get("flip_up"),
        flip_down=data.get("flip_down"),
        red_flags=data.get("red_flags"),
        confidence=data.get("confidence"),
        general_rule=data.get("general_rule"),
        disposition=disposition_label,
        disposition_reason=data.get("disposition_reason"),
    )
