"""
Central configuration for the RAG Document Assistant backend.
Every value can be overridden with an environment variable, so you can
tune behavior (chunk size, model, retrieval threshold, etc.) without
touching code.
"""
import os

# --- Chunking -----------------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))        # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))  # overlap between consecutive chunks

# --- Embeddings -----------------------------------------------------------
# all-MiniLM-L6-v2 is small (~80MB), fast on CPU, and good enough for
# document QA. Swap for a bigger model via env var if you want more accuracy.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Retrieval -----------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "4"))
# Cosine similarity (0..1) below which we don't even bother calling the LLM
# and instead report "not found in the document" directly.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.25"))

# --- LLM (Ollama) -----------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

# --- Uploads -----------------------------------------------------------
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
ALLOWED_EXTENSIONS = {"pdf", "txt"}

# --- Server / CORS -----------------------------------------------------------
# Restrict this in production; "*" is convenient for local development
# where the frontend is just an HTML file opened in the browser.
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
