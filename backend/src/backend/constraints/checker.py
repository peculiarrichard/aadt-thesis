"""Deterministic constraint checker (Section 9, build_plan.md task 8). Design,
rule grounding, and known limitations: docs/build_log.md task 8."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.disposition import DISPOSITION_SEVERITY_ORDER, DispositionClass

DEFAULT_RULES_PATH = Path(__file__).parent / "rules.yaml"

_RULE_TYPES = ("keyword", "blood_pressure_threshold")
_BP_PATTERN = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")
_NEGATION_CUES = ("no ", "not ", "denies", "denied", "without", "absent", "negative for")
_NEGATION_WINDOW = 25


@dataclass(frozen=True)
class ConstraintRule:
    rule_id: str
    description: str
    source_condition: str
    source_document: str
    minimum_disposition: DispositionClass
    rule_type: str
    trigger_clauses: list[list[str]]


@dataclass(frozen=True)
class ConstraintViolation:
    rule_id: str
    description: str
    minimum_disposition: DispositionClass


@dataclass(frozen=True)
class ConstraintCheckResult:
    passed: bool
    violations: list[ConstraintViolation]

    @property
    def escalation_required(self) -> bool:
        return not self.passed


def load_rules(path: Path = DEFAULT_RULES_PATH) -> list[ConstraintRule]:
    """Parse and validate the rule set. Raises ValueError on any schema violation
    (unknown minimum_disposition, unknown rule_type, duplicate rule_id, a keyword
    rule with no trigger_clauses, or an empty rule set)."""
    raw_rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = [_parse_rule(raw) for raw in raw_rules]
    _validate_rule_set(rules)
    return rules


@lru_cache(maxsize=1)
def _default_rules() -> tuple[ConstraintRule, ...]:
    return tuple(load_rules())


def _parse_rule(raw: dict[str, Any]) -> ConstraintRule:
    rule_id = raw["rule_id"]
    try:
        minimum_disposition = DispositionClass(raw["minimum_disposition"])
    except ValueError as exc:
        raise ValueError(
            f"rule {rule_id}: invalid minimum_disposition {raw['minimum_disposition']!r}, "
            f"expected one of {[d.value for d in DispositionClass]}"
        ) from exc

    rule_type = raw.get("rule_type", "keyword")
    if rule_type not in _RULE_TYPES:
        raise ValueError(f"rule {rule_id}: unknown rule_type {rule_type!r}, expected {_RULE_TYPES}")

    trigger_clauses = raw.get("trigger_clauses", [])
    if rule_type == "keyword" and not trigger_clauses:
        raise ValueError(f"rule {rule_id}: keyword rule must define trigger_clauses")

    return ConstraintRule(
        rule_id=rule_id,
        description=raw["description"],
        source_condition=raw["source_condition"],
        source_document=raw["source_document"],
        minimum_disposition=minimum_disposition,
        rule_type=rule_type,
        trigger_clauses=trigger_clauses,
    )


def _validate_rule_set(rules: list[ConstraintRule]) -> None:
    if not rules:
        raise ValueError("rule set is empty")
    ids = [rule.rule_id for rule in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("rule_id values must be unique")


def _keyword_present(keyword: str, lowered_text: str) -> bool:
    """Case-insensitive substring match with a negation guard: a match is discarded
    if a negation cue (see _NEGATION_CUES) appears in the _NEGATION_WINDOW characters
    immediately before it (e.g. "no jaundice" does not count as "jaundice" present)."""
    keyword = keyword.lower()
    for match in re.finditer(re.escape(keyword), lowered_text):
        window_start = max(0, match.start() - _NEGATION_WINDOW)
        preceding = lowered_text[window_start : match.start()]
        if any(cue in preceding for cue in _NEGATION_CUES):
            continue
        return True
    return False


def _blood_pressure_crisis(case_text: str) -> bool:
    """True if any systolic/diastolic pair in the text meets or exceeds the
    hypertensive-crisis threshold (systolic >=180 or diastolic >=120 mmHg)."""
    for match in _BP_PATTERN.finditer(case_text):
        systolic, diastolic = int(match.group(1)), int(match.group(2))
        if systolic >= 180 or diastolic >= 120:
            return True
    return False


def _rule_fires(rule: ConstraintRule, case_text: str) -> bool:
    if rule.rule_type == "blood_pressure_threshold":
        return _blood_pressure_crisis(case_text)

    lowered = case_text.lower()
    return any(
        all(_keyword_present(keyword, lowered) for keyword in clause)
        for clause in rule.trigger_clauses
    )


def check_constraints(
    case_text: str,
    draft_disposition: DispositionClass,
    rules: list[ConstraintRule] | None = None,
) -> ConstraintCheckResult:
    """Screen a draft disposition against every rule (Section 9). A rule only produces
    a violation when it fires on the case text *and* draft_disposition is less severe
    than the rule's minimum_disposition -- a rule that fires but the draft already
    meets or exceeds that severity is not a violation, since this checker exists to
    catch an under-triaged draft, not to second-guess an adequately severe one."""
    if rules is None:
        rules = list(_default_rules())

    draft_index = DISPOSITION_SEVERITY_ORDER.index(draft_disposition)
    violations = []
    for rule in rules:
        if not _rule_fires(rule, case_text):
            continue
        minimum_index = DISPOSITION_SEVERITY_ORDER.index(rule.minimum_disposition)
        if draft_index < minimum_index:
            violations.append(
                ConstraintViolation(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    minimum_disposition=rule.minimum_disposition,
                )
            )

    return ConstraintCheckResult(passed=not violations, violations=violations)
