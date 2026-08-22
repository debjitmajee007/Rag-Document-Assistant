"""
Step 5 + 7 of the pipeline: Vector Database and Similarity Search.

Each uploaded document gets its own FAISS index (IndexFlatIP — exact
inner-product search, which is cosine similarity since embeddings are
normalized). Indexes live in memory, keyed by a generated document_id,
so the server can hold multiple uploaded documents at once.

Note: this in-memory store resets when the server restarts. For a
persistent store, swap this module for a ChromaDB-backed implementation
(see README) without changing main.py's interface.
"""
from typing import Dict, List, Tuple

import faiss
import numpy as np


class DocumentStore:
    """FAISS index + the chunk text it was built from, for one document."""

    def __init__(self, embedding_dim: int):
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.chunks: List[str] = []
        # Kept separately (not just inside FAISS) so other features — like the
        # 3D PCA view — can work with the raw vectors directly.
        self.embeddings: np.ndarray = np.empty((0, embedding_dim), dtype="float32")

    def add(self, embeddings: np.ndarray, chunks: List[str]) -> None:
        self.index.add(embeddings)
        self.chunks.extend(chunks)
        self.embeddings = np.vstack([self.embeddings, embeddings])

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Tuple[int, str, float]]:
        """Return up to top_k (chunk_index, chunk_text, similarity_score) tuples, best first."""
        if len(self.chunks) == 0:
            return []
        query_embedding = np.expand_dims(query_embedding, axis=0)
        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                # FAISS pads results with -1 when the document has fewer than
                # top_k chunks — skip these rather than indexing with -1.
                continue
            results.append((int(idx), self.chunks[idx], float(score)))
        return results


# In-memory registry: document_id -> DocumentStore
_STORES: Dict[str, DocumentStore] = {}


def create_store(doc_id: str, embedding_dim: int) -> DocumentStore:
    store = DocumentStore(embedding_dim)
    _STORES[doc_id] = store
    return store


def get_store(doc_id: str) -> DocumentStore:
    if doc_id not in _STORES:
        raise KeyError(doc_id)
    return _STORES[doc_id]


def delete_store(doc_id: str) -> None:
    _STORES.pop(doc_id, None)
