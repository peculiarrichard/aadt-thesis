"""Privacy options 1+2, combined into one scan every case-save path runs
(option 4: before anything is persisted, never after). Regex redaction
(`deidentify.py`) catches pattern-shaped PII and is always applied,
unconditionally, to whatever text ends up saved -- a hard floor, not
something the doctor can override. The LLM review (`agents/pii_review_agent.py`)
catches what regex structurally can't, but is advisory: it's surfaced to the
doctor (`PrivacyScanResult.requires_review`), and her explicit per-case
attestation (option 3, `api/case_recording.py`'s `confirm_draft`) is what
actually lets a flagged case through -- a softer, reviewable signal doesn't
get to silently block her own clinical judgment the way a confirmed
hard-redaction floor does.
"""

from dataclasses import dataclass, field

from backend.agents.pii_review_agent import PiiReviewResult, review_for_identifiability
from backend.deidentify import deidentify_text


@dataclass(frozen=True)
class PrivacyScanResult:
    text: str
    redaction_summary: dict[str, int] = field(default_factory=dict)
    llm_flagged: bool = False
    llm_flag_details: str | None = None

    @property
    def requires_review(self) -> bool:
        return bool(self.redaction_summary) or self.llm_flagged


def scan_for_privacy_risk(text: str) -> PrivacyScanResult:
    """Runs on every case-save path (option 1: not just the patient-related
    ones) -- walkthrough text isn't supposed to involve a real patient, but
    nothing about free text typed or spoken by a human guarantees that, so
    this is a safety net, not a redundant check. Used on a raw transcript
    blob before it's handed to the structuring agent -- see
    `scan_fields_for_privacy_risk` for already-structured field dicts (form
    entry, bulk upload, the final re-scan at confirm-save)."""
    deidentified = deidentify_text(text)

    redaction_summary: dict[str, int] = {}
    for span in deidentified.redactions:
        redaction_summary[span.category] = redaction_summary.get(span.category, 0) + 1

    review = review_for_identifiability(deidentified.text)

    return PrivacyScanResult(
        text=deidentified.text,
        redaction_summary=redaction_summary,
        llm_flagged=review.flagged,
        llm_flag_details=review.details,
    )


# Every free-text field a case record can carry, in the *Case*-model/DB-column
# shape `case_upload_parsing.parse_record()` produces (not the raw walkthrough-
# JSON shape, e.g. `transcript_or_summary` here, not `case_text`) -- callers
# must scan post-parse_record, consistently, so these names actually match.
# PII can land in any of these, not just the main narrative (e.g.
# "factors_against_referral" naming a real relative is just as real a risk).
FREE_TEXT_FIELDS = (
    "transcript_or_summary",
    "doctor_reasoning_notes",
    "initial_impression",
    "examination_or_checks",
    "factors_toward_referral",
    "factors_against_referral",
    "flip_up",
    "flip_down",
    "red_flags",
    "confidence_notes",
    "general_rule",
)


def scan_fields_for_privacy_risk(fields: dict) -> tuple[dict, PrivacyScanResult]:
    """Regex-redacts every free-text field independently (always applied,
    unconditionally -- this is the hard safety floor), then runs one LLM
    identifiability check against all of them concatenated (not one call per
    field, to keep this to a single LLM call per case). Returns the
    redacted fields dict (safe to persist) and the combined scan result.
    `fields` must already be in `parse_record()`'s output shape (DB column
    names) -- call that first, then this, not the other way around."""
    redacted_fields = dict(fields)
    redaction_summary: dict[str, int] = {}

    for key in FREE_TEXT_FIELDS:
        value = fields.get(key)
        if not isinstance(value, str) or not value:
            continue
        deidentified = deidentify_text(value)
        redacted_fields[key] = deidentified.text
        for span in deidentified.redactions:
            redaction_summary[span.category] = redaction_summary.get(span.category, 0) + 1

    combined_text = "\n".join(
        str(redacted_fields[key]) for key in FREE_TEXT_FIELDS if redacted_fields.get(key)
    )
    review = (
        review_for_identifiability(combined_text)
        if combined_text
        else PiiReviewResult(flagged=False, details=None)
    )

    return redacted_fields, PrivacyScanResult(
        text=combined_text,
        redaction_summary=redaction_summary,
        llm_flagged=review.flagged,
        llm_flag_details=review.details,
    )
