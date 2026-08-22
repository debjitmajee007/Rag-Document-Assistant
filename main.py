"""
RAG Document Assistant — FastAPI backend.

Four features, one uploaded document at a time per document_id:
  1. Workspace & Chat     — upload, chunk, embed, retrieve, ask an LLM
  2. Knowledge Graph       — LLM-extracted entity/relation triples (GraphRAG-lite)
  3. 3D Vector Space       — PCA projection of the chunk embeddings
  4. Podcast               — LLM-written two-host script (read aloud client-side)

Run with:
  uvicorn main:app --reload --port 8000
"""
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import document_processor as docproc
import embeddings as emb
import graph_service as graphs
import llm_service as llm
import podcast_service as podcast
import vector_store as vs
import vectors3d_service as v3d

app = FastAPI(title="RAG Document Assistant", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metadata about uploaded documents, keyed by document_id. In-memory only —
# resets on server restart, same as the vector store and graph/podcast caches.
_DOCUMENTS: dict = {}


def _require_document(document_id: str) -> None:
    if document_id not in _DOCUMENTS:
        raise HTTPException(404, "Unknown document_id. Upload a document first.")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class UploadResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class AskRequest(BaseModel):
    document_id: str
    question: str


class SourceChunk(BaseModel):
    index: int
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str
    found: bool
    sources: List[SourceChunk]


class GraphNode(BaseModel):
    id: str
    weight: int


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    batches_processed: int
    batches_total: int


class Vector3DPoint(BaseModel):
    index: int
    x: float
    y: float
    z: float
    label: str


class Vectors3DResponse(BaseModel):
    points: List[Vector3DPoint]
    query_point: Optional[Vector3DPoint] = None


class PodcastLine(BaseModel):
    speaker: str
    text: str


class PodcastResponse(BaseModel):
    script: List[PodcastLine]


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# 1. Workspace & Chat
# --------------------------------------------------------------------------- #
@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Steps 1-5: extract text, clean it, chunk it, embed it, index it."""
    filename = file.filename or "upload"
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if extension not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only .pdf and .txt files are supported.")

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large (> {config.MAX_FILE_SIZE_MB} MB).")

    if extension == "pdf":
        raw_text = docproc.extract_text_from_pdf(file_bytes)
    else:
        raw_text = docproc.extract_text_from_txt(file_bytes)

    raw_text = docproc.clean_text(raw_text)
    if not raw_text:
        raise HTTPException(
            400,
            "No extractable text was found in this file. If it's a scanned "
            "PDF (images of text), OCR it first — this project reads text, not images.",
        )

    chunks = docproc.chunk_text(raw_text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    if not chunks:
        raise HTTPException(400, "Document text could not be split into chunks.")

    chunk_embeddings = emb.embed_texts(chunks)
    embedding_dim = int(chunk_embeddings.shape[1])

    document_id = str(uuid.uuid4())
    store = vs.create_store(document_id, embedding_dim)
    store.add(chunk_embeddings, chunks)

    _DOCUMENTS[document_id] = {
        "filename": filename,
        "chunk_count": len(chunks),
        "uploaded_at": time.time(),
    }

    return UploadResponse(document_id=document_id, filename=filename, chunk_count=len(chunks))


@app.get("/api/document/{document_id}/chunks")
def get_chunks(document_id: str):
    """Expose the chunk index (used by the Workspace source panel)."""
    _require_document(document_id)
    store = vs.get_store(document_id)
    return {"chunks": store.chunks}


@app.post("/api/ask", response_model=AskResponse)
def ask_question(payload: AskRequest):
    """Steps 6-9: embed the question, retrieve relevant chunks, ask the LLM."""
    _require_document(payload.document_id)

    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "Question must not be empty.")

    store = vs.get_store(payload.document_id)
    query_embedding = emb.embed_query(question)
    results = store.search(query_embedding, config.TOP_K)

    # Step 10: if nothing relevant enough was retrieved, say so without
    # even spending an LLM call.
    if not results or results[0][2] < config.SIMILARITY_THRESHOLD:
        return AskResponse(answer=llm.NOT_FOUND_MESSAGE, found=False, sources=[])

    context_chunks = [chunk for _idx, chunk, _score in results]

    try:
        answer = llm.ask_ollama(question, context_chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    found = llm.NOT_FOUND_MESSAGE.lower() not in answer.lower()
    sources = [SourceChunk(index=idx, text=chunk, score=round(score, 4)) for idx, chunk, score in results]
    return AskResponse(answer=answer, found=found, sources=sources)


# --------------------------------------------------------------------------- #
# 2. Knowledge Graph (GraphRAG-lite)
# --------------------------------------------------------------------------- #
@app.post("/api/document/{document_id}/graph/build", response_model=GraphResponse)
def build_graph(document_id: str):
    """
    Extracts entities/relationships from the document via the LLM. This
    costs one LLM call per batch of chunks, so it's a manual, explicit
    action rather than something that runs automatically on upload.
    """
    _require_document(document_id)
    store = vs.get_store(document_id)
    try:
        graph = graphs.build_graph(document_id, store.chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return graph


@app.get("/api/document/{document_id}/graph", response_model=GraphResponse)
def get_graph(document_id: str):
    _require_document(document_id)
    graph = graphs.get_graph(document_id)
    if graph is None:
        raise HTTPException(404, "Graph not built yet — POST to /graph/build first.")
    return graph


# --------------------------------------------------------------------------- #
# 3. 3D Vector Space
# --------------------------------------------------------------------------- #
@app.get("/api/document/{document_id}/vectors3d", response_model=Vectors3DResponse)
def get_vectors3d(document_id: str, q: Optional[str] = None):
    """
    PCA-projects every chunk embedding down to 3D. If a query string `q`
    is given, it's embedded and projected into the *same* PCA space so
    the frontend can show where a question lands relative to the chunks.
    """
    _require_document(document_id)
    store = vs.get_store(document_id)

    coords = v3d.project_to_3d(store.embeddings)
    points = [
        Vector3DPoint(index=i, x=float(c[0]), y=float(c[1]), z=float(c[2]), label=store.chunks[i][:100])
        for i, c in enumerate(coords)
    ]

    query_point = None
    if q and q.strip():
        query_embedding = emb.embed_query(q.strip())
        qc = v3d.project_query_to_3d(query_embedding, store.embeddings)
        query_point = Vector3DPoint(index=-1, x=float(qc[0]), y=float(qc[1]), z=float(qc[2]), label=q.strip())

    return Vectors3DResponse(points=points, query_point=query_point)


# --------------------------------------------------------------------------- #
# 4. Podcast (Matrix is a purely client-side visual effect — no endpoint)
# --------------------------------------------------------------------------- #
@app.post("/api/document/{document_id}/podcast", response_model=PodcastResponse)
def get_podcast(document_id: str):
    _require_document(document_id)
    store = vs.get_store(document_id)
    try:
        script = podcast.generate_podcast_script(store.chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    if not script:
        raise HTTPException(503, "The model didn't return a usable script. Try again.")
    return PodcastResponse(script=[PodcastLine(**line) for line in script])


# --------------------------------------------------------------------------- #
# Cleanup
# --------------------------------------------------------------------------- #
@app.delete("/api/document/{document_id}")
def delete_document(document_id: str):
    vs.delete_store(document_id)
    graphs.delete_graph(document_id)
    _DOCUMENTS.pop(document_id, None)
    return {"status": "deleted"}
