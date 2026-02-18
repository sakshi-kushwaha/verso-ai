import json
import logging
import re
import time
import httpx
from config import OLLAMA_HOST, LLM_MODEL, LLM_TIMEOUT
from prompts import (
    DOC_TYPE_PROMPT,
    SUBJECT_CATEGORY_PROMPT,
    REEL_GENERATION_PROMPT,
    REEL_SCRIPT_PROMPT,
    REEL_STYLE_INSTRUCTIONS,
    REEL_DEPTH_INSTRUCTIONS,
    REEL_USE_CASE_INSTRUCTIONS,
    DOC_TYPE_INSTRUCTIONS,
    FLASHCARD_DIFFICULTY_INSTRUCTIONS,
    REEL_FEW_SHOT,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 3


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
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))
        except httpx.TimeoutException as e:
            last_error = e
            log.warning("Ollama call timed out after %ss (attempt %d/%d)", timeout, attempt + 1, 1 + MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))

    if isinstance(last_error, httpx.ConnectError):
        raise OllamaUnavailableError(f"Cannot reach Ollama at {OLLAMA_HOST}") from last_error
    raise last_error


def detect_doc_type(text: str) -> str:
    """Detect document type from first 2000 chars."""
    try:
        prompt = DOC_TYPE_PROMPT.format(text=text[:2000])
        result = llm_call(prompt, timeout=120.0).strip().lower()
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
    """Detect subject category from first 2000 chars."""
    try:
        prompt = SUBJECT_CATEGORY_PROMPT.format(text=text[:2000])
        result = llm_call(prompt, timeout=120.0).strip().lower()
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

    max_parse_attempts = 3
    for attempt in range(max_parse_attempts):
        result = llm_call(prompt, json_mode=True, timeout=600.0)
        parsed = parse_llm_json(result)
        # If parse hit Level 3 fallback (title == "Summary"), retry unless last attempt
        if parsed["reels"] and parsed["reels"][0].get("title") == "Summary" and len(parsed["reels"]) == 1:
            if attempt < max_parse_attempts - 1:
                log.warning("LLM returned unparseable JSON (attempt %d/%d), retrying", attempt + 1, max_parse_attempts)
                time.sleep(min(2 ** attempt, 10))
                continue
        return parsed
    return parsed


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


def generate_reel_script(text: str, category: str, clips: list[dict]) -> dict | None:
    """Generate a multi-segment reel script using the LLM.

    Returns parsed dict with title, narration, segments — or None on failure.
    """
    if not clips:
        return None

    # Build numbered clip list for the prompt
    clip_list_lines = []
    for i, c in enumerate(clips, 1):
        clip_list_lines.append(f"{i}. {c['file']} — {c['description']}")
    clip_list = "\n".join(clip_list_lines)

    num_segments = 3 if len(text) < 800 else 4
    total_duration = 15

    prompt = REEL_SCRIPT_PROMPT.format(
        clip_list=clip_list,
        num_segments=num_segments,
        total_duration=total_duration,
        text=text[:2000],
    )

    try:
        result = llm_call(prompt, json_mode=True, timeout=300.0)
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Reel script generation failed (LLM error)")
        return None

    # Parse JSON
    parsed = None
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", result)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not parsed or "segments" not in parsed:
        log.warning("Reel script generation returned invalid JSON")
        return None

    # Validate segments
    valid_filenames = {c["file"] for c in clips}
    validated_segments = []
    for seg in parsed["segments"]:
        if not isinstance(seg, dict):
            continue
        clip_file = seg.get("clip", "")
        if clip_file not in valid_filenames:
            continue
        dur = seg.get("duration", 5)
        if not isinstance(dur, (int, float)) or dur < 2:
            dur = max(2, dur if isinstance(dur, (int, float)) else 5)
        validated_segments.append({
            "clip": clip_file,
            "overlay": str(seg.get("overlay", ""))[:60],
            "duration": float(dur),
        })

    if len(validated_segments) < 2:
        log.warning("Reel script has too few valid segments (%d)", len(validated_segments))
        return None

    # Normalize durations to sum to total_duration
    dur_sum = sum(s["duration"] for s in validated_segments)
    if dur_sum > 0 and abs(dur_sum - total_duration) > 0.5:
        scale = total_duration / dur_sum
        for s in validated_segments:
            s["duration"] = round(s["duration"] * scale, 1)

    parsed["segments"] = validated_segments
    parsed.setdefault("title", "")
    parsed.setdefault("narration", "")

    log.info("Generated reel script: %d segments, title=%r", len(validated_segments), parsed["title"][:40])
    return parsed
