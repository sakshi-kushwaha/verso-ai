import json
import re
import httpx
from config import OLLAMA_HOST, LLM_MODEL, LLM_TIMEOUT
from prompts import DOC_TYPE_PROMPT, REEL_GENERATION_PROMPT


def llm_call(prompt: str) -> str:
    """Single LLM call to Ollama. Returns response text."""
    resp = httpx.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def detect_doc_type(text: str) -> str:
    """Detect document type from first 2000 chars."""
    prompt = DOC_TYPE_PROMPT.format(text=text[:2000])
    result = llm_call(prompt).strip().lower()

    valid = {"textbook", "research_paper", "business", "fiction", "technical", "general"}
    for v in valid:
        if v in result:
            return v
    return "general"


def generate_reels(text: str, doc_type: str) -> dict:
    """Generate reels and flashcards from text. Returns parsed JSON with fallback."""
    prompt = REEL_GENERATION_PROMPT.format(text=text[:3000], doc_type=doc_type)
    result = llm_call(prompt)
    return parse_llm_json(result)


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output with multi-level fallback."""
    # Level 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Level 2: Extract JSON block from text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Level 3: Fallback — raw text as single reel
    return {
        "reels": [{"title": "Summary", "summary": text[:500], "category": "general", "keywords": ""}],
        "flashcards": [],
    }
