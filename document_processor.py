"""
Step 2 + 3 of the pipeline: Text Extraction and Chunking.

- extract_text_from_pdf / extract_text_from_txt turn raw uploaded bytes
  into a single plain-text string.
- chunk_text splits that string into overlapping, sentence-aware chunks
  that are small enough to embed meaningfully but large enough to carry
  real context.
"""
import io
import re
from typing import List

from pypdf import PdfReader


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from every page of a PDF and join it with newlines."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode a plain-text file, tolerating non-UTF-8 encodings."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def clean_text(text: str) -> str:
    """Normalize whitespace so chunking behaves predictably."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """
    Split text into overlapping chunks along sentence boundaries where
    possible, so a chunk rarely ends mid-sentence. Falls back to a hard
    character split for any single sentence longer than chunk_size.

    Overlap means the tail of one chunk reappears at the start of the
    next, which helps the retriever find answers that straddle a chunk
    boundary.
    """
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
            continue

        if current:
            chunks.append(current)

        overlap_text = current[-overlap:] if overlap > 0 else ""
        current = f"{overlap_text} {sentence}".strip()

        # A single sentence longer than chunk_size: hard-split it.
        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            current = current[max(chunk_size - overlap, 1):]

    if current:
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]
