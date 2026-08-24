from functools import lru_cache

from sentence_transformers import SentenceTransformer

# Section 8: BGE-M3 embeddings, 1024-dim dense output (see backend.db.models.EMBEDDING_DIM).
MODEL_NAME = "BAAI/bge-m3"


@lru_cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Dense embeddings for a batch of texts, one 1024-dim vector per input text."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()
