"""Real smoke test for the BGE-M3 embedding integration (Section 8).

Skipped by default: downloads the real model (~2.5GB) and its torch dependency. Run
explicitly with `RUN_EMBEDDING_SMOKE_TEST=1 uv run pytest tests/test_embeddings_smoke.py`
(see docs/setup.md). This proves the integration works; it does not embed the full
guideline corpus — see docs/build_plan.md for that gap.
"""

import os

import pytest

# sentence_transformers (and the torch import behind it) is deferred into each test
# body, not imported at module level: pytest imports every test module at collection
# time regardless of skip markers, and that import alone costs 100s of seconds on a
# cold environment. Importing it here would slow down every `pytest` run, not just
# this file, even when these tests are skipped.

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
