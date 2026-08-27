"""Real BGE-M3 smoke test, skipped by default. See docs/setup.md to run it."""

import os

import pytest

# Deferred into each test body: pytest imports every module at collection time
# regardless of skip markers, and this import alone costs 100s of seconds.
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMBEDDING_SMOKE_TEST") != "1",
    reason="downloads the real BGE-M3 model (~2.5GB); set RUN_EMBEDDING_SMOKE_TEST=1 to run",
)


def test_embed_texts_returns_correct_dimension_and_is_deterministic():
    from backend.db.models import EMBEDDING_DIM
    from backend.ingestion.embeddings import embed_texts

    vectors = embed_texts(["fever and headache", "chest pain"])

    assert len(vectors) == 2
    assert all(len(v) == EMBEDDING_DIM for v in vectors)

    repeat = embed_texts(["fever and headache"])
    assert repeat[0] == pytest.approx(vectors[0], abs=1e-5)


def test_embed_texts_handles_empty_input():
    from backend.ingestion.embeddings import embed_texts

    assert embed_texts([]) == []
