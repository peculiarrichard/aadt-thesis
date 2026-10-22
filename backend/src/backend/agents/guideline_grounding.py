"""Layer 4 guideline grounding: nearest-chunk vector retrieval over the embedded
guideline corpus, then condition nodes are read off whichever chunks come back
(same BGE-M3 index built by the ingestion pipeline, reused rather than a second
retrieval mechanism)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.enums import GraphRelationType
from backend.db.models import (
    GuidelineChunk,
    GuidelineDocument,
    GuidelineGraphEdge,
    GuidelineGraphNode,
)

DEFAULT_CHUNK_K = 3
_MAX_EVIDENCE_ITEMS = 5

# Empirically calibrated against the real corpus: distances for genuinely
# related real case text cluster ~0.41-0.44, an unrelated control query ~0.49 --
# the gap is narrow, so this is a tuned cutoff, not a clean separation.
MAX_RELEVANT_DISTANCE = 0.46


@dataclass(frozen=True)
class GuidelineMatch:
    condition: str
    symptoms: list[str]
    recommendations: list[str]
    document_source: str


def retrieve_guideline_evidence(
    session: Session, query_embedding: list[float], k: int = DEFAULT_CHUNK_K
) -> list[GuidelineMatch]:
    distance_expr = GuidelineChunk.embedding.cosine_distance(query_embedding)
    rows = session.execute(
        select(GuidelineChunk, distance_expr.label("distance"))
        .where(GuidelineChunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(k)
    ).all()

    matches: list[GuidelineMatch] = []
    seen_conditions: set[uuid.UUID] = set()
    for chunk, distance in rows:
        if distance > MAX_RELEVANT_DISTANCE:
            continue
        for condition_id, symptom_ids, recommendation_ids in _conditions_for_chunk(
            session, chunk.chunk_id
        ):
            if condition_id in seen_conditions:
                continue
            seen_conditions.add(condition_id)
            condition_node = session.get(GuidelineGraphNode, condition_id)
            document = session.get(GuidelineDocument, condition_node.document_id)
            matches.append(
                GuidelineMatch(
                    condition=condition_node.label,
                    symptoms=_labels_for(session, symptom_ids)[:_MAX_EVIDENCE_ITEMS],
                    recommendations=_labels_for(session, recommendation_ids)[:_MAX_EVIDENCE_ITEMS],
                    document_source=document.source if document else "unknown",
                )
            )
    return matches


def _conditions_for_chunk(
    session: Session, chunk_id: uuid.UUID
) -> list[tuple[uuid.UUID, list[uuid.UUID], list[uuid.UUID]]]:
    edges = (
        session.execute(select(GuidelineGraphEdge).where(GuidelineGraphEdge.chunk_id == chunk_id))
        .scalars()
        .all()
    )
    by_condition: dict[uuid.UUID, tuple[list[uuid.UUID], list[uuid.UUID]]] = {}
    for edge in edges:
        symptom_ids, recommendation_ids = by_condition.setdefault(edge.source_node_id, ([], []))
        if edge.relation_type == GraphRelationType.PRESENTS_WITH:
            symptom_ids.append(edge.target_node_id)
        elif edge.relation_type == GraphRelationType.RECOMMENDS:
            recommendation_ids.append(edge.target_node_id)
    return [(cid, s, r) for cid, (s, r) in by_condition.items()]


def _labels_for(session: Session, node_ids: list[uuid.UUID]) -> list[str]:
    if not node_ids:
        return []
    nodes = (
        session.execute(select(GuidelineGraphNode).where(GuidelineGraphNode.node_id.in_(node_ids)))
        .scalars()
        .all()
    )
    return [node.label for node in nodes]
