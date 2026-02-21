from __future__ import annotations

import json
import logging
import re
import time
import httpx
from config import OLLAMA_HOST, LLM_MODEL, CLASSIFICATION_MODEL, REEL_MODEL, LLM_TIMEOUT
from database import get_db
from prompts import (
    DOC_TYPE_PROMPT,
    SUBJECT_CATEGORY_PROMPT,
    COMBINED_CLASSIFICATION_PROMPT,
    DOC_SUMMARY_PROMPT,
    REEL_GENERATION_PROMPT,
    REEL_SYSTEM_PROMPT,
    REEL_SCRIPT_PROMPT,
    REEL_MIXED_SCRIPT_PROMPT,
    TOPIC_EXTRACTION_PROMPT,
    TOPIC_REEL_PROMPT,
    TOPIC_REEL_WITH_CLIPS_PROMPT,
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
            "num_ctx": 2048,
            "num_predict": 400,
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


def clean_classification_response(text: str) -> str:
    """Clean qwen3 response — remove think tags and extract single word."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()
    first_word = text.split()[0].lower().rstrip('.,;:') if text else ""
    return first_word


def classification_llm_call(prompt: str, timeout: float = 60.0) -> str:
    """LLM call using the lightweight classification model (thinking disabled)."""
    payload = {
        "model": CLASSIFICATION_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 2048,
            "num_predict": 20,
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
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))
        except httpx.TimeoutException as e:
            last_error = e
            log.warning("Classification call timed out after %ss (attempt %d/%d)", timeout, attempt + 1, 1 + MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))

    if isinstance(last_error, httpx.ConnectError):
        raise OllamaUnavailableError(f"Cannot reach Ollama at {OLLAMA_HOST}") from last_error
    raise last_error


def reel_llm_call(prompt: str, timeout: float = 600.0, system: str = None,
                   num_predict: int = 800, json_mode: bool = True) -> str:
    """LLM call using the reel model. JSON mode on by default."""
    payload = {
        "model": REEL_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_ctx": 2048,
            "num_predict": num_predict,
            "repeat_penalty": 1.1,
        },
    }
    if json_mode:
        payload["format"] = "json"
    if system:
        payload["system"] = system

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            result = resp.json()["response"]
            return result
        except httpx.ConnectError as e:
            last_error = e
            log.warning("Ollama connection failed (attempt %d/%d): %s", attempt + 1, 1 + MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))
        except httpx.TimeoutException as e:
            last_error = e
            log.warning("Reel LLM call timed out after %ss (attempt %d/%d)", timeout, attempt + 1, 1 + MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))

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


def detect_doc_classification(text: str) -> tuple[str, str]:
    """Detect both doc type and subject category in a single LLM call.

    Returns (doc_type, subject_category) tuple.
    """
    valid_doc_types = {"textbook", "research_paper", "business", "fiction", "technical", "general"}

    try:
        prompt = COMBINED_CLASSIFICATION_PROMPT.format(text=text[:2000])
        raw = classification_llm_call(prompt)
        cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        words = cleaned.lower().split()
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Combined classification failed, defaulting to general/general")
        return ("general", "general")

    doc_type = "general"
    subject = "general"

    for w in words:
        w = w.rstrip('.,;:')
        if w in valid_doc_types and doc_type == "general":
            doc_type = w
        elif w in VALID_CATEGORIES and subject == "general":
            subject = w

    return (doc_type, subject)


def generate_doc_summary(full_text: str) -> str | None:
    """Generate a document-level summary (~10 sentences) for the uploads table.

    Uses LLM_MODEL (qwen2.5:3b) in plain text mode — no JSON formatting.
    Returns the summary string, or None if generation fails.
    """
    prompt = DOC_SUMMARY_PROMPT.format(text=full_text[:6000])
    try:
        result = reel_llm_call(prompt, timeout=120.0, num_predict=300, json_mode=False)
        summary = result.strip()
        if summary and len(summary) > 50 and len(summary) < 3000:
            return summary
        log.warning("Doc summary output looks malformed (%d chars), discarding", len(summary) if summary else 0)
        return None
    except (OllamaUnavailableError, httpx.TimeoutException) as e:
        log.warning("Doc summary generation failed: %s", e)
        return None


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
        result = reel_llm_call(prompt, system=REEL_SYSTEM_PROMPT)
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


def _sample_document(full_text: str, max_chars: int = 6000) -> str:
    """Sample text from beginning, middle, and end of a document.

    For short docs (<= max_chars), returns the full text.
    For longer docs, takes roughly equal chunks from start, middle, and end
    so the LLM sees the full breadth of topics covered.
    """
    if len(full_text) <= max_chars:
        return full_text

    chunk = max_chars // 3
    start = full_text[:chunk]
    mid_start = (len(full_text) - chunk) // 2
    middle = full_text[mid_start:mid_start + chunk]
    end = full_text[-chunk:]
    return f"{start}\n\n[...]\n\n{middle}\n\n[...]\n\n{end}"


def extract_topics(full_text: str, num_topics: int = 5) -> list[dict]:
    """Extract key topics from document text using LLM.

    Returns list of {"topic": "...", "keywords": "..."} dicts.
    """
    sampled = _sample_document(full_text, max_chars=6000)
    prompt = TOPIC_EXTRACTION_PROMPT.format(
        text=sampled,
        num_topics=num_topics,
    )

    # Scale num_predict with topic count (each topic needs ~30 tokens)
    predict = max(400, num_topics * 50)
    try:
        result = reel_llm_call(prompt, timeout=120.0, num_predict=predict)
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Topic extraction failed — LLM unavailable")
        return []

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

    if not parsed or "topics" not in parsed:
        log.warning("Topic extraction returned invalid JSON")
        return []

    topics = []
    for t in parsed["topics"]:
        if isinstance(t, dict) and "topic" in t:
            topics.append({
                "topic": str(t["topic"])[:100],
                "keywords": str(t.get("keywords", "")),
            })

    log.info("Extracted %d topics from document", len(topics))
    return topics[:num_topics]


def gather_topic_content(topic: dict, full_text: str, max_chars: int = 3000) -> str:
    """Gather text relevant to a topic from the full document.

    Scores each paragraph by keyword overlap and returns the most relevant ones.
    """
    keywords = [k.strip().lower() for k in topic["keywords"].split(",") if k.strip()]
    topic_words = topic["topic"].lower().split()
    all_keywords = set(keywords + topic_words)

    paragraphs = [p.strip() for p in full_text.split("\n") if len(p.strip()) > 30]
    if not paragraphs:
        return full_text[:max_chars]

    scored = []
    for para in paragraphs:
        lower = para.lower()
        score = sum(1 for kw in all_keywords if kw in lower)
        if score > 0:
            scored.append((score, para))

    scored.sort(key=lambda x: -x[0])

    # Take top paragraphs up to max_chars
    collected = []
    total = 0
    for _, para in scored:
        if total + len(para) > max_chars:
            break
        collected.append(para)
        total += len(para)

    if not collected:
        return full_text[:max_chars]

    return "\n".join(collected)


def get_gold_few_shot(category: str = "general") -> str:
    """Fetch gold standard reels from DB as dynamic few-shot examples.

    Queries for reels matching the category. Falls back to any gold reels,
    then to the static REEL_FEW_SHOT constant if DB has none.
    """
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT title, summary, narration, category, keywords, source_text "
            "FROM reels WHERE upload_id = ("
            "  SELECT id FROM uploads WHERE filename = '__gold_standard__' LIMIT 1"
            ") AND LOWER(category) = LOWER(?) LIMIT 2",
            (category,),
        ).fetchall()

        if not rows:
            rows = conn.execute(
                "SELECT title, summary, narration, category, keywords, source_text "
                "FROM reels WHERE upload_id = ("
                "  SELECT id FROM uploads WHERE filename = '__gold_standard__' LIMIT 1"
                ") ORDER BY RANDOM() LIMIT 2",
            ).fetchall()

        conn.close()

        if not rows:
            return REEL_FEW_SHOT

        examples = []
        for i, row in enumerate(rows, 1):
            source = (row["source_text"] or row["summary"] or "")[:300]
            output = json.dumps({
                "reels": [{
                    "title": row["title"],
                    "summary": row["summary"],
                    "narration": row["narration"],
                    "category": row["category"],
                    "keywords": row["keywords"],
                }],
                "flashcards": [],
            })
            examples.append(f'Example {i}:\nInput: "{source}"\nOutput: {output}')

        result = "\n\n".join(examples)
        log.info("Dynamic few-shot: %d examples for category=%s", len(examples), category)
        return result

    except Exception as e:
        log.warning("Failed to fetch gold few-shot examples: %s — using static fallback", e)
        return REEL_FEW_SHOT


def generate_topic_reel(topic: str, topic_text: str, doc_type: str, prefs: dict, category: str = "general") -> dict:
    """Generate a single reel + flashcards for one topic.

    Returns parsed dict with "reels" and "flashcards" arrays.
    """
    few_shot = get_gold_few_shot(category)
    prompt = TOPIC_REEL_PROMPT.format(
        topic=topic,
        text=topic_text[:3000],
        doc_type=doc_type,
        doc_type_instruction=DOC_TYPE_INSTRUCTIONS.get(doc_type, DOC_TYPE_INSTRUCTIONS["general"]),
        style_instruction=REEL_STYLE_INSTRUCTIONS.get(prefs.get("learning_style", "mixed"), REEL_STYLE_INSTRUCTIONS["mixed"]),
        depth_instruction=REEL_DEPTH_INSTRUCTIONS.get(prefs.get("content_depth", "balanced"), REEL_DEPTH_INSTRUCTIONS["balanced"]),
        use_case_instruction=REEL_USE_CASE_INSTRUCTIONS.get(prefs.get("use_case", "learning"), REEL_USE_CASE_INSTRUCTIONS["learning"]),
        difficulty_instruction=FLASHCARD_DIFFICULTY_INSTRUCTIONS.get(prefs.get("flashcard_difficulty", "medium"), FLASHCARD_DIFFICULTY_INSTRUCTIONS["medium"]),
        few_shot=few_shot,
    )

    result = reel_llm_call(prompt)
    return parse_llm_json(result)


def generate_topic_reel_with_clips(
    topic: str, topic_text: str, doc_type: str, prefs: dict,
    category: str, clips: list[dict],
) -> dict:
    """Generate a single reel with video clip selections + flashcards in ONE LLM call.

    Merges generate_topic_reel + generate_reel_script into a single call.
    Returns parsed dict with "reels" (including segments) and "flashcards".
    """
    few_shot = get_gold_few_shot(category)

    # Build clip list for the prompt
    clip_list_lines = []
    for i, c in enumerate(clips, 1):
        clip_list_lines.append(f"{i}. {c['file']} — {c.get('description', 'stock footage')}")
    clip_list = "\n".join(clip_list_lines)

    num_segments = 3 if len(topic_text) < 800 else 4

    prompt = TOPIC_REEL_WITH_CLIPS_PROMPT.format(
        topic=topic,
        text=topic_text[:3000],
        doc_type=doc_type,
        doc_type_instruction=DOC_TYPE_INSTRUCTIONS.get(doc_type, DOC_TYPE_INSTRUCTIONS["general"]),
        style_instruction=REEL_STYLE_INSTRUCTIONS.get(prefs.get("learning_style", "mixed"), REEL_STYLE_INSTRUCTIONS["mixed"]),
        depth_instruction=REEL_DEPTH_INSTRUCTIONS.get(prefs.get("content_depth", "balanced"), REEL_DEPTH_INSTRUCTIONS["balanced"]),
        use_case_instruction=REEL_USE_CASE_INSTRUCTIONS.get(prefs.get("use_case", "learning"), REEL_USE_CASE_INSTRUCTIONS["learning"]),
        difficulty_instruction=FLASHCARD_DIFFICULTY_INSTRUCTIONS.get(prefs.get("flashcard_difficulty", "medium"), FLASHCARD_DIFFICULTY_INSTRUCTIONS["medium"]),
        few_shot=few_shot,
        clip_list=clip_list,
        num_segments=num_segments,
        total_duration=15,
    )

    result = reel_llm_call(prompt, system=REEL_SYSTEM_PROMPT)
    return parse_llm_json(result)


def generate_reel_script(text: str, category: str, clips: list[dict],
                         narration: str = "") -> dict | None:
    """Generate a multi-segment reel script using the LLM.

    Returns parsed dict with title, narration, segments — or None on failure.
    """
    if not clips:
        return None

    # Build numbered clip list for the prompt
    clip_list_lines = []
    for i, c in enumerate(clips, 1):
        clip_list_lines.append(f"{i}. {c['file']}")
    clip_list = "\n".join(clip_list_lines)

    num_segments = 3 if len(text) < 800 else 4
    total_duration = 15

    prompt = REEL_SCRIPT_PROMPT.format(
        clip_list=clip_list,
        narration=narration[:1500] if narration else text[:500],
        num_segments=num_segments,
        total_duration=total_duration,
        text=text[:2000],
    )

    try:
        result = reel_llm_call(prompt, timeout=300.0)
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


def generate_mixed_reel_script(
    text: str, category: str, clips: list[dict], images: list[dict],
) -> dict | None:
    """Generate a reel script with mixed video clips and images.

    The LLM decides which segments use video clips (for action/motion) and
    which use images with text overlays (for key facts/concepts).
    Returns parsed dict with title, narration, segments — or None on failure.
    Falls back to video-only generate_reel_script() if images unavailable.
    """
    if not clips:
        return None
    if not images:
        return generate_reel_script(text, category, clips)

    # Build numbered clip list
    clip_list_lines = []
    for i, c in enumerate(clips, 1):
        desc = c.get("description", "stock footage")
        clip_list_lines.append(f"{i}. {c['file']} — {desc}")
    clip_list = "\n".join(clip_list_lines)

    # Build numbered image list
    image_list_lines = []
    for i, img in enumerate(images[:6], 1):  # Cap at 6 to keep prompt short
        image_list_lines.append(f"{i}. {img['file']}")
    image_list = "\n".join(image_list_lines)

    num_segments = 3 if len(text) < 800 else 4
    total_duration = 15

    prompt = REEL_MIXED_SCRIPT_PROMPT.format(
        clip_list=clip_list,
        image_list=image_list,
        num_segments=num_segments,
        total_duration=total_duration,
        text=text[:2000],
    )

    try:
        result = reel_llm_call(prompt, timeout=300.0)
    except (OllamaUnavailableError, httpx.TimeoutException):
        log.warning("Mixed reel script generation failed, falling back to video-only")
        return generate_reel_script(text, category, clips)

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
        log.warning("Mixed reel script returned invalid JSON, falling back to video-only")
        return generate_reel_script(text, category, clips)

    # Validate segments — accept both video and image types
    valid_clip_files = {c["file"] for c in clips}
    valid_image_files = {img["file"] for img in images}
    image_path_map = {img["file"]: img["path"] for img in images}

    validated_segments = []
    for seg in parsed["segments"]:
        if not isinstance(seg, dict):
            continue

        seg_type = seg.get("type", "video")
        dur = seg.get("duration", 5)
        if not isinstance(dur, (int, float)) or dur < 2:
            dur = max(2, dur if isinstance(dur, (int, float)) else 5)

        if seg_type == "image":
            img_file = seg.get("image", "")
            if img_file not in valid_image_files:
                continue
            validated_segments.append({
                "type": "image",
                "image": img_file,
                "image_path": image_path_map[img_file],
                "text": str(seg.get("text", ""))[:80],
                "duration": float(dur),
            })
        else:
            clip_file = seg.get("clip", "")
            if clip_file not in valid_clip_files:
                continue
            validated_segments.append({
                "type": "video",
                "clip": clip_file,
                "duration": float(dur),
            })

    if len(validated_segments) < 2:
        log.warning("Mixed script has too few valid segments (%d), falling back", len(validated_segments))
        return generate_reel_script(text, category, clips)

    # Normalize durations to sum to total_duration
    dur_sum = sum(s["duration"] for s in validated_segments)
    if dur_sum > 0 and abs(dur_sum - total_duration) > 0.5:
        scale = total_duration / dur_sum
        for s in validated_segments:
            s["duration"] = round(s["duration"] * scale, 1)

    parsed["segments"] = validated_segments
    parsed.setdefault("title", "")
    parsed.setdefault("narration", "")

    n_vid = sum(1 for s in validated_segments if s.get("type") == "video")
    n_img = sum(1 for s in validated_segments if s.get("type") == "image")
    log.info("Generated mixed reel script: %d segments (%d video, %d image), title=%r",
             len(validated_segments), n_vid, n_img, parsed["title"][:40])
    return parsed
