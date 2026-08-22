"""
Step 4 of the pipeline: Embeddings.

Wraps a Sentence Transformers model so the rest of the app just calls
embed_texts() / embed_query() without knowing which model is loaded.
Embeddings are L2-normalized so that cosine similarity can be computed
with a plain inner product (faster, and what FAISS's IndexFlatIP does).
"""
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

import config

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazily load the embedding model (downloaded once, then cached locally)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a batch of texts. Returns a (n, dim) float32 array, normalized."""
    model = get_model()
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.astype("float32")


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string. Returns a (dim,) float32 vector."""
    return embed_texts([query])[0]
