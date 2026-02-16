import httpx
from config import OLLAMA_HOST, LLM_MODEL, LLM_TIMEOUT
from prompts import DOC_TYPE_PROMPT


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
