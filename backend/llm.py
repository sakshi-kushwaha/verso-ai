import json
import logging
import re
import httpx
from config import OLLAMA_HOST, LLM_MODEL, CLASSIFICATION_MODEL, LLM_TIMEOUT
from prompts import (
    DOC_TYPE_PROMPT,
    SUBJECT_CATEGORY_PROMPT,
    REEL_GENERATION_PROMPT,
    REEL_STYLE_INSTRUCTIONS,
    REEL_DEPTH_INSTRUCTIONS,
    REEL_USE_CASE_INSTRUCTIONS,
    DOC_TYPE_INSTRUCTIONS,
    FLASHCARD_DIFFICULTY_INSTRUCTIONS,
    REEL_FEW_SHOT,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 1


class OllamaUnavailableError(Exception):
    """Raised when Ollama cannot be reached after retries."""


def llm_call(prompt: str, json_mode: bool = False, timeout: float = None) -> str:
    """Single LLM call to Ollama with retry. Returns response text.

    Raises OllamaUnavailableError if Ollama is unreachable after retries.
    Raises httpx.TimeoutException if the call times out after retries.
    """
    if timeout is None:
        timeout = LLM_TIMEOUT

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_ctx": 4096,
            "repeat_penalty": 1.1,
        },
    }
    if json_mode:
        payload["format"] = "json"

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except httpx.ConnectError as e:
            last_error = e
            log.warning("Ollama connection failed (attempt %d/%d): %s", attempt + 1, 1 + MAX_RETRIES, e)
        except httpx.TimeoutException as e:
            last_error = e
            log.warning("Ollama call timed out after %ss (attempt %d/%d)", timeout, attempt + 1, 1 + MAX_RETRIES)

    if isinstance(last_error, httpx.ConnectError):
        raise OllamaUnavailableError(f"Cannot reach Ollama at {OLLAMA_HOST}") from last_error
    raise last_error


def clean_classification_response(text: str) -> str:
    """Clean qwen3 response — remove think tags and extract single word."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()
    first_word = text.split()[0].lower().rstrip('.,;:') if text else ""
    return first_word


def classification_llm_call(prompt: str, timeout: float = 60.0) -> str:
    """LLM call using the lightweight classification model with /no_think."""
    payload = {
        "model": CLASSIFICATION_MODEL,
        "prompt": "/no_think " + prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 2048,
        },
    }

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except httpx.ConnectError as e:
            last_error = e
            log.warning("Ollama connection failed (attempt %d/%d): %s", attempt + 1, 1 + MAX_RETRIES, e)
        except httpx.TimeoutException as e:
            last_error = e
            log.warning("Classification call timed out after %ss (attempt %d/%d)", timeout, attempt + 1, 1 + MAX_RETRIES)

    if isinstance(last_error, httpx.ConnectError):
        raise OllamaUnavailableError(f"Cannot reach Ollama at {OLLAMA_HOST}") from last_error
    raise last_error


def detect_doc_type(text: str) -> str:
    """Detect document type from first 2000 chars using classification model."""
    try:
        prompt = DOC_TYPE_PROMPT.format(text=text[:2000])
        raw = classification_llm_call(prompt)
        result = clean_classification_response(raw)
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Doc type detection failed, defaulting to 'general'")
        return "general"

    valid = {"textbook", "research_paper", "business", "fiction", "technical", "general"}
    for v in valid:
        if v in result:
            return v
    return "general"


VALID_CATEGORIES = {"science", "math", "history", "literature", "business", "technology", "medicine", "law", "arts", "engineering", "general"}


def detect_subject_category(text: str) -> str:
    """Detect subject category from first 2000 chars using classification model."""
    try:
        prompt = SUBJECT_CATEGORY_PROMPT.format(text=text[:2000])
        raw = classification_llm_call(prompt)
        result = clean_classification_response(raw)
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Subject category detection failed, defaulting to 'general'")
        return "general"

    for v in VALID_CATEGORIES:
        if v in result:
            return v
    return "general"


def generate_reels(text: str, doc_type: str, prefs: dict = None) -> dict:
    """Generate reels and flashcards from text with personalization.

    Raises OllamaUnavailableError if Ollama is down.
    """
    if prefs is None:
        prefs = {
            "learning_style": "mixed",
            "content_depth": "balanced",
            "use_case": "learning",
            "flashcard_difficulty": "medium",
        }

    prompt = REEL_GENERATION_PROMPT.format(
        text=text[:3000],
        doc_type=doc_type,
        doc_type_instruction=DOC_TYPE_INSTRUCTIONS.get(doc_type, DOC_TYPE_INSTRUCTIONS["general"]),
        style_instruction=REEL_STYLE_INSTRUCTIONS.get(prefs.get("learning_style", "mixed"), REEL_STYLE_INSTRUCTIONS["mixed"]),
        depth_instruction=REEL_DEPTH_INSTRUCTIONS.get(prefs.get("content_depth", "balanced"), REEL_DEPTH_INSTRUCTIONS["balanced"]),
        use_case_instruction=REEL_USE_CASE_INSTRUCTIONS.get(prefs.get("use_case", "learning"), REEL_USE_CASE_INSTRUCTIONS["learning"]),
        difficulty_instruction=FLASHCARD_DIFFICULTY_INSTRUCTIONS.get(prefs.get("flashcard_difficulty", "medium"), FLASHCARD_DIFFICULTY_INSTRUCTIONS["medium"]),
        few_shot=REEL_FEW_SHOT,
    )
    result = llm_call(prompt, json_mode=True, timeout=600.0)
    return parse_llm_json(result)


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output with validation and multi-level fallback."""
    parsed = None

    # Level 1: Direct JSON parse
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Level 2: Extract JSON block from text
    if parsed is None:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Level 3: Fallback — raw text as single reel
    if parsed is None:
        return {
            "reels": [{"title": "Summary", "summary": text[:500], "category": "general", "keywords": ""}],
            "flashcards": [],
        }

    # Validate structure
    if "reels" not in parsed:
        parsed["reels"] = []
    if "flashcards" not in parsed:
        parsed["flashcards"] = []

    # Validate each reel has required fields
    validated_reels = []
    for reel in parsed["reels"]:
        if isinstance(reel, dict) and "title" in reel and "summary" in reel:
            reel.setdefault("narration", reel["summary"])
            reel.setdefault("category", "general")
            reel.setdefault("keywords", "")
            validated_reels.append(reel)
    parsed["reels"] = validated_reels

    # Validate each flashcard
    validated_fcs = []
    for fc in parsed["flashcards"]:
        if isinstance(fc, dict) and "question" in fc and "answer" in fc:
            validated_fcs.append(fc)
    parsed["flashcards"] = validated_fcs

    return parsed
