"""
3D Vector Space.

Projects the document's high-dimensional chunk embeddings (384-dim for
all-MiniLM-L6-v2) down to 3 dimensions with PCA so they can be plotted
and rotated in the browser. Implemented with plain numpy SVD so no extra
dependency (e.g. scikit-learn) is needed beyond what embeddings.py
already requires.
"""
from typing import Tuple

import numpy as np


def _fit_pca(vectors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (mean, top-3 principal components) for a (n, d) array."""
    mean = vectors.mean(axis=0)
    centered = vectors - mean
    # Economy SVD: centered = U @ diag(S) @ Vt
    _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:3]  # (3, d) — top 3 principal axes
    return mean, components


def project_to_3d(vectors: np.ndarray) -> np.ndarray:
    """Project (n, d) embeddings down to (n, 3) via PCA."""
    if vectors.shape[0] == 0:
        return np.empty((0, 3))
    if vectors.shape[0] < 2:
        # PCA is undefined for a single point — just place it at the origin.
        return np.zeros((vectors.shape[0], 3))

    mean, components = _fit_pca(vectors)
    centered = vectors - mean
    n_components = components.shape[0]
    projected = centered @ components.T
    if n_components < 3:
        # Pad with zeros if the document is too small to have 3 real axes of variance.
        pad = np.zeros((projected.shape[0], 3 - n_components))
        projected = np.hstack([projected, pad])
    return projected


def project_query_to_3d(query_vector: np.ndarray, doc_vectors: np.ndarray) -> np.ndarray:
    """Project a single query embedding into the same PCA space as doc_vectors."""
    if doc_vectors.shape[0] < 2:
        return np.zeros(3)
    mean, components = _fit_pca(doc_vectors)
    centered = query_vector - mean
    n_components = components.shape[0]
    projected = centered @ components.T
    if n_components < 3:
        projected = np.concatenate([projected, np.zeros(3 - n_components)])
    return projected
