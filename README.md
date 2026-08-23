<div align="center">
AetherRAG — Document Assistant

A fully local Retrieval-Augmented Generation system. Upload a document, ask it questions, and get answers grounded strictly in that document — with a knowledge graph, a 3D embedding explorer, and an AI-generated podcast built on top.

Show Image Show Image Show Image Show Image Show Image

</div>
Overview

AetherRAG lets you upload a PDF or TXT file and interact with it four different ways — all running locally, with no document data or API calls ever leaving your machine.

Feature	What it does
Workspace & Chat	Ask questions, get answers grounded strictly in the document — or a clear "not found" when it isn't there
Knowledge Graph	See the document's key entities and relationships, extracted by the LLM
3D Vector Space	Explore the document's chunk embeddings, projected into 3D via PCA
Podcast & Matrix	A two-host podcast script summarizing the document, read aloud by your browser

No document ever leaves your machine, and no API key is required — the LLM is a local Ollama model.

How it works
PDF / TXT Upload → Text Extraction → Chunking → Embeddings → Vector DB (FAISS)
                                                                    │
                                          ┌─────────────────────────┼─────────────────────────┐
                                          ▼                         ▼                          ▼
                                  Similarity Search      Entity/Relation Extraction   PCA → 3D Projection
                                          │                         │
                                          ▼                         ▼
                                    Local LLM (Ollama)      Local LLM (Ollama)
                                          │                         │
                                     Answer / Podcast script   Knowledge Graph
Extraction — text is pulled from the uploaded PDF/TXT.
Chunking — split into overlapping, sentence-aware chunks (no sentence gets cut in half).
Embedding — each chunk is converted to a vector with Sentence Transformers.
Indexing — vectors go into a FAISS index, one per uploaded document.
Retrieval — a question is embedded and matched against the stored chunks by cosine similarity.
Generation — matched chunks are passed to a local LLM, which answers strictly from that context — or the app reports nothing relevant was found, without even calling the model.
Tech stack
Layer	Technology
Backend	FastAPI, Python
Embeddings	Sentence Transformers (all-MiniLM-L6-v2)
Vector store	FAISS
LLM	Ollama (Llama 3.2), fully local
Knowledge graph	LLM-extracted entity/relation triples, rendered with vis-network
3D visualization	NumPy PCA, rendered with Plotly
Podcast playback	Browser SpeechSynthesis API — no server-side TTS
Frontend	HTML, Tailwind CSS, vanilla JavaScript
Getting started
Prerequisites
Python 3.10+
Ollama installed and running locally
A modern browser (Chrome/Edge recommended for the best SpeechSynthesis voice support)

Pull a model and start Ollama:

bash
ollama pull llama3.2
ollama serve
Backend
bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

Check it's running: open http://localhost:8000/api/health — you should see {"status": "ok"}.

The first upload downloads the all-MiniLM-L6-v2 embedding model (~80MB) — this needs internet once, then it's cached locally.

Frontend
bash
cd frontend
python -m http.server 5500

Open http://localhost:5500 in your browser.

Usage
Workspace & Chat — drop a PDF or TXT file, wait for it to be indexed, then ask questions. Each answer shows the exact chunks it was grounded in, with similarity scores — click one to jump to it in the index.
Knowledge Graph — click "Build Knowledge Graph" to extract entities and relationships from the document.
3D Vector Space — explore chunks plotted by semantic similarity, or type a question to see where it lands relative to the document.
Podcast & Matrix — generate a two-host script and press play; toggle Matrix Mode for a rain-effect visualizer.
Project structure
rag-document-assistant/
├── backend/
│   ├── main.py                 # FastAPI app — all routes
│   ├── config.py                # Tunable settings
│   ├── document_processor.py    # PDF/TXT extraction + chunking
│   ├── embeddings.py            # Sentence Transformers wrapper
│   ├── vector_store.py          # FAISS index per document
│   ├── llm_service.py           # Ollama calls
│   ├── graph_service.py         # Knowledge Graph extraction
│   ├── vectors3d_service.py     # PCA projection for 3D view
│   ├── podcast_service.py       # Podcast script generation
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
Configuration

All environment variables, read by backend/config.py:

Variable	Default	Description
CHUNK_SIZE	800	Characters per chunk
CHUNK_OVERLAP	150	Overlap between consecutive chunks
EMBEDDING_MODEL	all-MiniLM-L6-v2	Any Sentence Transformers model name
TOP_K	4	Chunks retrieved per question
SIMILARITY_THRESHOLD	0.25	Below this, "not found" is returned without calling the LLM
OLLAMA_HOST	http://localhost:11434	Where Ollama is running
OLLAMA_MODEL	llama3.2	Which pulled model to use
MAX_FILE_SIZE_MB	20	Upload size limit
Limitations
In-memory storage — documents, graphs, and vector indexes reset when the backend restarts.
Knowledge Graph extraction is capped at 12 chunk batches by default to bound LLM cost on long documents.
Podcast audio quality depends on your browser/OS voices, since it's generated client-side.
Scanned/image-only PDFs are not supported — this reads embedded text, not images.
License

This project is licensed under the MIT License.

<div align="center">

Built with FastAPI, FAISS, Sentence Transformers, and Ollama — 100% local, no API keys required.

</div>
