"""Privacy option 2: an LLM-based check for real-patient identifiability,
layered on top of the regex-based `deidentify_text` (which only catches
pattern-shaped PII -- names with a title, emails, phone numbers, dates,
addresses). This catches what regex structurally can't: indirect references
("my neighbor's daughter"), a named clinic, a unique combination of details
that would identify someone even with no name attached.

Flags for human review -- never auto-redacts. A false positive here just
means a doctor re-reads her own case text once more; a false negative in an
auto-redaction would silently and incorrectly alter her clinical narrative.
Fails safe: any parse failure is treated as flagged, not as clean, since the
whole point of this check is catching what we're not sure about.
"""

import json
from dataclasses import dataclass

from backend.llm.client import chat_completion

_SYSTEM_PROMPT = (
    "You are a privacy reviewer for a medical research system. The clinician-specific "
    "case data this system stores must never identify a real, specific patient -- it is "
    "either a hypothetical/generalized case walkthrough, or an already de-identified "
    "summary. Read the text and decide: does it reference a real, identifiable patient? "
    "This includes not just names, but anything that could identify a specific real "
    "person -- a named clinic or workplace, a unique combination of details, an indirect "
    "reference like 'my neighbor's son' or 'the patient from last Tuesday'. Generic "
    "clinical language ('a 40-year-old woman with fever') is NOT identifying on its own.\n\n"
    'Respond with ONLY a single JSON object: {"flagged": true or false, "details": '
    '"<a short, specific explanation of what you flagged, or null if not flagged>"}'
)

_RETRY_NUDGE = (
    "Your previous response was not valid JSON matching the required schema. Respond "
    "again with ONLY the JSON object, no markdown fences, no other text."
)


@dataclass(frozen=True)
class PiiReviewResult:
    flagged: bool
    details: str | None


def review_for_identifiability(text: str) -> PiiReviewResult:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": text},
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

    # Fail safe: can't confirm this is clean, so treat it as flagged rather
    # than silently letting it through.
    return PiiReviewResult(
        flagged=True,
        details="Automatic privacy check could not be completed -- please review this text.",
    )


def _try_parse(raw: str) -> PiiReviewResult | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or "flagged" not in data:
        return None

    flagged = data["flagged"]
    if not isinstance(flagged, bool):
        return None

    details = data.get("details")
    return PiiReviewResult(flagged=flagged, details=str(details) if details else None)
