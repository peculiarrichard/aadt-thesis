"""Rule-based PII redaction. Limitations: docs/build_log.md task 4."""

import re
import uuid
from dataclasses import dataclass, field


@dataclass
class RedactionSpan:
    category: str
    original: str


@dataclass
class DeidentificationResult:
    text: str
    redactions: list[RedactionSpan] = field(default_factory=list)


_TITLES = r"(?:Mr|Mrs|Miss|Ms|Dr|Chief|Alhaji|Alhaja|Prince|Princess|Engr|Barr|Prof)\."
_NAME_PATTERN = re.compile(rf"\b{_TITLES}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}")
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Nigerian mobile numbers: 0<network prefix><8 digits>, or the same with +234/234
# in place of the leading 0.
_PHONE_PATTERN = re.compile(r"\b(?:\+?234|0)[7-9][01]\d{8}\b")
# Applied after PHONE below, so an already-redacted phone number's digits are gone
# by the time this runs — ordering alone avoids double-matching, no lookahead needed.
_NATIONAL_ID_PATTERN = re.compile(r"\b\d{11}\b")
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
_ADDRESS_PATTERN = re.compile(
    r"\b(?:No\.?\s*\d+[,]?\s+)?[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3}\s+"
    r"(?:Street|Road|Avenue|Close|Crescent|Estate|Lane|Way)\b"
)

# Order matters: NAME/EMAIL/PHONE run before the broad NATIONAL_ID digit pattern so
# a phone number's digits are already redacted (and thus invisible to that pattern)
# by the time it runs.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("NAME", _NAME_PATTERN),
    ("EMAIL", _EMAIL_PATTERN),
    ("PHONE", _PHONE_PATTERN),
    ("NATIONAL_ID", _NATIONAL_ID_PATTERN),
    ("DATE", _DATE_PATTERN),
    ("ADDRESS", _ADDRESS_PATTERN),
]


def deidentify_text(text: str) -> DeidentificationResult:
    """Redact detected PII spans, replacing each with `[REDACTED:<CATEGORY>]`."""
    redactions: list[RedactionSpan] = []
    result = text

    for category, pattern in _PATTERNS:

        def _replace(match: re.Match[str], category: str = category) -> str:
            redactions.append(RedactionSpan(category=category, original=match.group(0)))
            return f"[REDACTED:{category}]"

        result = pattern.sub(_replace, result)

    return DeidentificationResult(text=result, redactions=redactions)


def generate_patient_ref() -> str:
    """A pseudonymous, non-identifying reference for `consultations.patient_ref`
    (Section 7). Generated independently of any PII in the transcript — even a
    perfect scrub of the text wouldn't make it safe to derive patient_ref from
    patient-supplied content, so this never reads the transcript at all."""
    return f"PT-{uuid.uuid4().hex[:10]}"
