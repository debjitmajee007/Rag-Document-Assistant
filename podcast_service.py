"""
Podcast & Matrix tab — the "Podcast" half.

Generates a short two-host dialogue script summarizing the uploaded
document. Audio playback happens entirely client-side via the browser's
built-in SpeechSynthesis API, so no server-side TTS engine or audio
file generation is needed here — this module only produces the script.
"""
import json
import re
from typing import Dict, List

import llm_service as llm

PODCAST_PROMPT = """You are a podcast script writer. Based only on the DOCUMENT EXCERPTS \
below, write a short, engaging two-host podcast conversation (Host A and Host B) \
discussing the document's key points. 6 to 10 exchanges total, alternating speakers. \
Keep each line under 40 words. Do not invent facts that aren't in the excerpts.

Return ONLY a JSON array, no markdown fences, no commentary, in exactly this form:
[{{"speaker": "Host A", "text": "..."}}, {{"speaker": "Host B", "text": "..."}}]

DOCUMENT EXCERPTS:
{content}
"""


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def generate_podcast_script(chunks: List[str], max_chars: int = 6000) -> List[Dict[str, str]]:
    """Ask the LLM for a two-host dialogue script grounded in the document's chunks."""
    content = "\n\n".join(chunks)[:max_chars]
    prompt = PODCAST_PROMPT.format(content=content)
    raw = llm.generate_raw(prompt, temperature=0.4)
    raw = _strip_code_fence(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        script = [
            {"speaker": str(item.get("speaker", "Host A")).strip() or "Host A",
             "text": str(item.get("text", "")).strip()}
            for item in data
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        ]
        if script:
            return script

    # Fallback: the model didn't return valid JSON — surface its raw text as
    # a single line rather than silently returning nothing.
    return [{"speaker": "Host A", "text": raw}] if raw else []
