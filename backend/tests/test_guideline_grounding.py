"""Vector-retrieval tests for guideline grounding -- the query embedding is
supplied directly (no real BGE-M3 call needed), same pattern as the rest of
this project's DB-backed tests that fake precedent embeddings. Requires
`docker compose up -d`; skips otherwise. Fixture label is deliberately not a
real condition name, to avoid colliding with the real ingested corpus."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.guideline_grounding import retrieve_guideline_evidence
from backend.db.enums import GraphNodeType, GraphRelationType
from backend.db.models import (
    EMBEDDING_DIM,
    GuidelineChunk,
    GuidelineDocument,
    GuidelineGraphEdge,
    GuidelineGraphNode,
)
from backend.db.session import SessionLocal

# A unit vector in the first dimension -- its distance to itself is exactly 0,
# the global minimum, so it's guaranteed to rank ahead of every real corpus
# chunk regardless of what's actually ingested.
_FIXTURE_EMBEDDING = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
# Orthogonal to the fixture embedding -- cosine distance 1.0, far outside
# MAX_RELEVANT_DISTANCE no matter what else is in the corpus.
_UNRELATED_EMBEDDING = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        session.execute(select(1))
    except OperationalError:
        session.close()
        pytest.skip("database not reachable; run `docker compose up -d` to enable this test")

    document = GuidelineDocument(title="Test Fixture Guideline", source="test-fixture")
    session.add(document)
    session.flush()

    condition = GuidelineGraphNode(
        document_id=document.document_id,
        node_type=GraphNodeType.CONDITION,
        label="ZZZTEST FIXTURE CONDITION",
    )
    symptom = GuidelineGraphNode(
        document_id=document.document_id,
        node_type=GraphNodeType.SYMPTOM,
        label="Impaired consciousness",
    )
    recommendation = GuidelineGraphNode(
        document_id=document.document_id,
        node_type=GraphNodeType.RECOMMENDATION,
        label="Artemisinin-based combination therapy",
    )
    session.add_all([condition, symptom, recommendation])
    chunk = GuidelineChunk(
        document_id=document.document_id, content="fixture chunk", embedding=_FIXTURE_EMBEDDING
    )
    session.add(chunk)
    session.flush()

    session.add_all(
        [
            GuidelineGraphEdge(
                source_node_id=condition.node_id,
                target_node_id=symptom.node_id,
                relation_type=GraphRelationType.PRESENTS_WITH,
                chunk_id=chunk.chunk_id,
            ),
            GuidelineGraphEdge(
                source_node_id=condition.node_id,
                target_node_id=recommendation.node_id,
                relation_type=GraphRelationType.RECOMMENDS,
                chunk_id=chunk.chunk_id,
            ),
        ]
    )
    session.commit()

    try:
        yield session
    finally:
        session.execute(
            delete(GuidelineGraphEdge).where(GuidelineGraphEdge.chunk_id == chunk.chunk_id)
        )
        session.execute(
            delete(GuidelineChunk).where(GuidelineChunk.document_id == document.document_id)
        )
        session.execute(
            delete(GuidelineGraphNode).where(GuidelineGraphNode.document_id == document.document_id)
        )
        session.execute(
            delete(GuidelineDocument).where(GuidelineDocument.document_id == document.document_id)
        )
        session.commit()
        session.close()


def test_retrieve_guideline_evidence_returns_linked_symptoms_and_recommendations(db_session):
    matches = retrieve_guideline_evidence(db_session, _FIXTURE_EMBEDDING)

    fixture_matches = [m for m in matches if m.condition == "ZZZTEST FIXTURE CONDITION"]
    assert len(fixture_matches) == 1
    match = fixture_matches[0]
    assert match.symptoms == ["Impaired consciousness"]
    assert match.recommendations == ["Artemisinin-based combination therapy"]
    assert match.document_source == "test-fixture"


def test_retrieve_guideline_evidence_returns_nothing_for_an_unrelated_embedding(db_session):
    matches = retrieve_guideline_evidence(db_session, _UNRELATED_EMBEDDING)

    assert all(m.condition != "ZZZTEST FIXTURE CONDITION" for m in matches)
