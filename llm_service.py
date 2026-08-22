"""
All calls to the local LLM (via Ollama) go through this module.

- _call_ollama(): shared low-level request + error handling.
- generate_raw(): arbitrary prompt in, plain text out. Used by the graph
  extractor and the podcast script writer.
- ask_ollama(): the RAG question-answering call — wraps the shared caller
  with the grounded-in-context system instructions.
"""
from typing import List

import requests

import config

NOT_FOUND_MESSAGE = "The information was not found in the document."

SYSTEM_INSTRUCTIONS = f"""You are a precise document question-answering assistant.
Answer the user's question using ONLY the information in the CONTEXT below.

Rules:
- Do not use outside knowledge and do not make anything up.
- If the answer is not contained in the context, respond EXACTLY with:
  "{NOT_FOUND_MESSAGE}"
- Otherwise, answer concisely and stay strictly grounded in the context.
- You may reference short phrases from the context, but explain in your own words.
"""


def _call_ollama(prompt: str, temperature: float = 0.1) -> str:
    """Shared low-level call to Ollama's /api/generate endpoint."""
    try:
        response = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=config.OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()

    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to Ollama at "
            f"{config.OLLAMA_HOST}. Make sure Ollama is installed and running "
            f"(`ollama serve`), and that the model has been pulled "
            f"(`ollama pull {config.OLLAMA_MODEL}`)."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            "The request to Ollama timed out. Try a smaller/faster model, or "
            "increase OLLAMA_TIMEOUT_SECONDS."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"Ollama returned an error ({exc}). Check that model "
            f"'{config.OLLAMA_MODEL}' exists locally (`ollama list`)."
        ) from exc


def generate_raw(prompt: str, temperature: float = 0.3) -> str:
    """Send an arbitrary prompt to the local model and return plain text."""
    return _call_ollama(prompt, temperature=temperature)


def build_prompt(question: str, context_chunks: List[str]) -> str:
    if context_chunks:
        context = "\n\n---\n\n".join(
            f"[Excerpt {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
        )
    else:
        context = "(no relevant context was retrieved)"

    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )


def ask_ollama(question: str, context_chunks: List[str]) -> str:
    """The RAG question-answering call: grounded strictly in retrieved context."""
    prompt = build_prompt(question, context_chunks)
    answer = _call_ollama(prompt, temperature=0.1)
    return answer or NOT_FOUND_MESSAGE
