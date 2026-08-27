"""Unit tests for the matching heuristic (no DB) plus a DB-backed integration test.
Requires `docker compose up -d`; skips otherwise. Fixture label is deliberately
not a real condition name, to avoid colliding with the real ingested corpus."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from backend.agents.guideline_grounding import condition_matches_text, retrieve_guideline_evidence
from backend.db.enums import GraphNodeType, GraphRelationType
from backend.db.models import (
    GuidelineChunk,
    GuidelineDocument,
    GuidelineGraphEdge,
    GuidelineGraphNode,
)
from backend.db.session import SessionLocal

# --- pure matching heuristic -------------------------------------------------


def test_single_word_label_matches_substring():
    assert condition_matches_text("MALARIA", "rdt positive for malaria")


def test_multi_word_label_matches_on_any_significant_word():
    assert condition_matches_text("DIABETES MELLITUS", "family history of diabetes in mother")


def test_no_match_when_no_significant_word_present():
    assert not condition_matches_text("TETANUS", "patient has a mild headache")


def test_short_words_in_label_are_not_used_as_signal():
    # "OF" and "THE" are below the significant-token length threshold; only
    # "TORSION"/"TESTIS" can drive a match.
    assert not condition_matches_text("TORSION OF THE TESTIS", "an unrelated case about the ear")
    assert condition_matches_text("TORSION OF THE TESTIS", "left testis high-riding")


# --- DB-backed retrieval ------------------------------------------------------


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
    chunk = GuidelineChunk(document_id=document.document_id, content="fixture chunk")
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
    matches = retrieve_guideline_evidence(db_session, "fever, zzztest fixture condition present")

    fixture_matches = [m for m in matches if m.condition == "ZZZTEST FIXTURE CONDITION"]
    assert len(fixture_matches) == 1
    match = fixture_matches[0]
    assert match.symptoms == ["Impaired consciousness"]
    assert match.recommendations == ["Artemisinin-based combination therapy"]
    assert match.document_source == "test-fixture"


def test_retrieve_guideline_evidence_returns_nothing_for_unrelated_text(db_session):
    matches = retrieve_guideline_evidence(db_session, "patient here for a routine dental check")

    assert all(m.condition != "ZZZTEST FIXTURE CONDITION" for m in matches)
