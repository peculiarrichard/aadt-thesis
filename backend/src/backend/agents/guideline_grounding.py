"""Layer 4 guideline grounding (Section 5.4): graph-based retrieval, not vector
similarity (full-corpus embedding isn't run yet). Design notes: docs/build_log.md
task 9."""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.enums import GraphNodeType, GraphRelationType
from backend.db.models import GuidelineDocument, GuidelineGraphEdge, GuidelineGraphNode

_MIN_TOKEN_LEN = 5
_MAX_EVIDENCE_ITEMS = 5


@dataclass(frozen=True)
class GuidelineMatch:
    condition: str
    symptoms: list[str]
    recommendations: list[str]
    document_source: str


def _significant_tokens(label: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]+", label.lower()) if len(token) >= _MIN_TOKEN_LEN}


def condition_matches_text(label: str, lowered_case_text: str) -> bool:
    """Pure matching function, unit-tested independently of the database."""
    tokens = _significant_tokens(label)
    if not tokens:
        return label.lower() in lowered_case_text
    return any(token in lowered_case_text for token in tokens)


def retrieve_guideline_evidence(session: Session, case_text: str) -> list[GuidelineMatch]:
    """Matching CONDITION nodes with their linked symptoms/recommendations."""
    lowered = case_text.lower()
    condition_nodes = (
        session.execute(
            select(GuidelineGraphNode).where(
                GuidelineGraphNode.node_type == GraphNodeType.CONDITION
            )
        )
        .scalars()
        .all()
    )

    matches: list[GuidelineMatch] = []
    for node in condition_nodes:
        if not condition_matches_text(node.label, lowered):
            continue

        edges = (
            session.execute(
                select(GuidelineGraphEdge).where(GuidelineGraphEdge.source_node_id == node.node_id)
            )
            .scalars()
            .all()
        )
        symptom_ids = [
            e.target_node_id for e in edges if e.relation_type == GraphRelationType.PRESENTS_WITH
        ]
        recommendation_ids = [
            e.target_node_id for e in edges if e.relation_type == GraphRelationType.RECOMMENDS
        ]

        document = session.get(GuidelineDocument, node.document_id)
        matches.append(
            GuidelineMatch(
                condition=node.label,
                symptoms=_labels_for(session, symptom_ids)[:_MAX_EVIDENCE_ITEMS],
                recommendations=_labels_for(session, recommendation_ids)[:_MAX_EVIDENCE_ITEMS],
                document_source=document.source if document else "unknown",
            )
        )
    return matches


def _labels_for(session: Session, node_ids: list) -> list[str]:
    if not node_ids:
        return []
    nodes = (
        session.execute(select(GuidelineGraphNode).where(GuidelineGraphNode.node_id.in_(node_ids)))
        .scalars()
        .all()
    )
    return [node.label for node in nodes]
