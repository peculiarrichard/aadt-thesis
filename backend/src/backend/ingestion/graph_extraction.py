"""Deterministic heading/keyword extraction of condition -> symptom/recommendation
relations from guideline text (Section 5.3's graph-based retrieval requirement).

Uses the source documents' own structure rather than any model call: an ALL-CAPS line
is treated as a condition heading, and a fixed vocabulary of Title-Case subheading
labels ("Clinical features", "Treatment objectives", ...) tags the lines that follow
them, until the next label or heading. Verified against the real Nigeria STG text
(docs/guideline_corpus/nigeria_stg.pdf): these exact labels appear 100-200+ times each.

Known limitation: this assumes a label's content immediately follows it in reading
order. Source PDFs with a multi-column layout (as pypdf extracts them linearly) can
interleave a condition's labels and its content across columns, so extraction from
those documents is expected to be sparse, not exhaustive — see
docs/guideline_corpus/README.md.
"""

from dataclasses import dataclass, field

_HEADING_MIN_LEN = 3
_HEADING_MAX_LEN = 60

SYMPTOM_LABELS = {"clinical features"}
RECOMMENDATION_LABELS = {"treatment objectives", "non-drug treatment", "drug treatment"}
_OTHER_KNOWN_LABELS = {
    "introduction",
    "differential diagnoses",
    "complications",
    "investigations",
    "surgery",
    "caution",
    "causes",
    "prevention",
    "notable adverse drug reactions",
}
KNOWN_LABELS = SYMPTOM_LABELS | RECOMMENDATION_LABELS | _OTHER_KNOWN_LABELS


@dataclass
class ConditionRelations:
    condition: str
    symptoms: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _is_condition_heading(stripped: str) -> bool:
    if not (_HEADING_MIN_LEN <= len(stripped) <= _HEADING_MAX_LEN):
        return False
    if stripped.lower() in KNOWN_LABELS:
        return False
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def extract_condition_relations(lines: list[str]) -> list[ConditionRelations]:
    """Extract condition -> symptom/recommendation relations from a block of lines
    (typically one chunk's lines, so results can be attributed to that chunk for
    provenance). Conditions with no symptoms or recommendations attributed are
    dropped — this also filters out non-condition ALL-CAPS lines (chapter titles,
    "FOREWORD", etc.), which never accumulate any labeled content.
    """
    results: list[ConditionRelations] = []
    current: ConditionRelations | None = None
    current_label: str | None = None

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue

        if _is_condition_heading(stripped):
            current = ConditionRelations(condition=stripped)
            results.append(current)
            current_label = None
            continue

        lower = stripped.lower()
        if lower in KNOWN_LABELS:
            current_label = lower
            continue

        if current is None:
            continue

        if current_label in SYMPTOM_LABELS:
            current.symptoms.append(stripped)
        elif current_label in RECOMMENDATION_LABELS:
            current.recommendations.append(stripped)

    return [r for r in results if r.symptoms or r.recommendations]
