"""
Knowledge Graph (GraphRAG-lite).

Rather than a separate graph database, this asks the local LLM to pull
(source, relation, target) triples out of batches of the document's own
chunks, then merges them into a plain node/edge structure the frontend
can render with a force-directed graph. Results are cached in memory per
document_id since extraction costs one LLM call per batch and shouldn't
re-run on every page view.
"""
import json
import re
from typing import Dict, List, Optional

import llm_service as llm

EXTRACTION_PROMPT = """Extract the key entities (people, places, organizations, concepts) \
and the relationships between them from the TEXT below.

Return ONLY a JSON array, with no markdown fences and no commentary, in exactly this form:
[{{"source": "Entity A", "relation": "short relation phrase", "target": "Entity B"}}]

Rules:
- Use short, consistent names for the same entity every time it appears.
- Extract at most 8 triples from this text.
- If the text has no clear relationships, return [].

TEXT:
{text}
"""

# In-memory cache: document_id -> {"nodes": [...], "edges": [...]}
_GRAPH_CACHE: Dict[str, dict] = {}


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def _extract_triples(text: str) -> List[dict]:
    raw = llm.generate_raw(EXTRACTION_PROMPT.format(text=text), temperature=0.0)
    raw = _strip_code_fence(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict) and t.get("source") and t.get("target")]


def build_graph(
    document_id: str,
    chunks: List[str],
    batch_size: int = 3,
    max_batches: int = 12,
) -> dict:
    """
    Extract triples from the document (grouping chunks into batches to limit
    LLM calls) and cache the resulting graph. Re-running overwrites the cache.
    """
    batches = ["\n".join(chunks[i:i + batch_size]) for i in range(0, len(chunks), batch_size)]

    all_triples: List[dict] = []
    for batch in batches[:max_batches]:
        all_triples.extend(_extract_triples(batch))

    nodes: Dict[str, dict] = {}
    edges: List[dict] = []
    seen_edges = set()

    for triple in all_triples:
        source = str(triple.get("source", "")).strip()
        target = str(triple.get("target", "")).strip()
        relation = str(triple.get("relation", "")).strip() or "related to"
        if not source or not target or source == target:
            continue

        nodes.setdefault(source, {"id": source, "weight": 0})
        nodes.setdefault(target, {"id": target, "weight": 0})
        nodes[source]["weight"] += 1
        nodes[target]["weight"] += 1

        edge_key = (source, target, relation)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({"source": source, "target": target, "label": relation})

    graph = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "batches_processed": min(len(batches), max_batches),
        "batches_total": len(batches),
    }
    _GRAPH_CACHE[document_id] = graph
    return graph


def get_graph(document_id: str) -> Optional[dict]:
    return _GRAPH_CACHE.get(document_id)


def delete_graph(document_id: str) -> None:
    _GRAPH_CACHE.pop(document_id, None)
