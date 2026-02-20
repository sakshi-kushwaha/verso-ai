import logging
import os
import random
import asyncio
import threading
from database import get_db
import httpx
from parser import parse_document, EmptyDocumentError, ScannedPDFError
from llm import (
    detect_doc_type, detect_subject_category, generate_doc_summary,
    generate_reel_script, generate_topic_reel,
    OllamaUnavailableError,
)
from bg_images import assign_images, _resolve_category
from rag import embed_chunks
from video import compose_reel_video, compose_multi_clip_reel, get_clips_for_category, get_images_for_category
from tts.engine import generate_audio
from config import STOCK_VIDEOS_DIR
from ws_manager import manager

log = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
PAGES_PER_CHUNK = 3

# Set by main.py lifespan — the running asyncio event loop
_event_loop: asyncio.AbstractEventLoop | None = None


def process_upload(upload_id: int, filepath: str, user_id: int = 1):
    """Run the full pipeline in a background thread."""
    thread = threading.Thread(target=_run_pipeline, args=(upload_id, filepath, user_id), daemon=True)
    thread.start()


def _get_user_prefs(user_id: int) -> dict:
    """Fetch user preferences for personalized reel generation."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT learning_style, content_depth, use_case, flashcard_difficulty "
            "FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {
            "learning_style": "mixed",
            "content_depth": "balanced",
            "use_case": "learning",
            "flashcard_difficulty": "medium",
        }
    return dict(row)


def _pick_stock_video(reel_category: str, upload_category: str, used_clips: set | None = None) -> str | None:
    """Pick a random stock video matching the reel's category, avoiding already-used clips."""
    cat = _resolve_category(reel_category, upload_category)
    folder = STOCK_VIDEOS_DIR / cat
    if not folder.is_dir():
        folder = STOCK_VIDEOS_DIR / "general"
    if not folder.is_dir():
        return None
    videos = [f for f in folder.iterdir() if f.suffix.lower() == ".mp4"]
    if not videos:
        return None
    if used_clips is not None:
        available = [f for f in videos if f.name not in used_clips]
        if not available:
            # All used — reset and allow reuse
            used_clips.clear()
            available = videos
        pick = random.choice(available)
        used_clips.add(pick.name)
        return str(pick)
    return str(random.choice(videos))


def _try_compose_video(reel_id: int, reel: dict, subject_category: str, used_clips: set | None = None):
    """Try to compose a video for a reel. Tries multi-clip first, falls back to single-clip."""
    cat = _resolve_category(reel.get("category", ""), subject_category)

    # Generate TTS from narration — voice rotates by reel_id for variety
    tts_path = None
    narration = reel.get("narration", reel.get("summary", ""))
    if narration:
        try:
            tts_path = generate_audio(narration, reel_index=reel_id)
        except Exception:
            log.debug("TTS failed for reel %d, composing without narration", reel_id)

    # Try multi-clip composition first
    try:
        clips = get_clips_for_category(cat)
        images = get_images_for_category(cat)
        if clips and len(clips) >= 2:
            # Filter out already-used clips to avoid repetition across reels
            if used_clips is not None:
                available_clips = [c for c in clips if c["file"] not in used_clips]
                if len(available_clips) < 2:
                    # Not enough fresh clips — reset and allow reuse
                    used_clips.clear()
                    available_clips = clips
            else:
                available_clips = clips
            script = generate_reel_script(
                text=reel.get("summary", ""),
                category=cat,
                clips=available_clips,
                images=images or None,
            )
            if script and script.get("segments"):
                video_path = compose_multi_clip_reel(
                    reel_id=reel_id,
                    title=script.get("title", reel.get("title", "")),
                    narration=script.get("narration", narration or ""),
                    segments=script["segments"],
                    category=cat,
                    tts_audio_path=str(tts_path) if tts_path else None,
                )
                # Track which clips were used
                if used_clips is not None:
                    for seg in script["segments"]:
                        used_clips.add(seg.get("clip", ""))
                conn = get_db()
                conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
                conn.commit()
                conn.close()
                log.info("Composed multi-clip video for reel %d: %s", reel_id, video_path)
                return video_path
    except Exception as e:
        log.warning("Multi-clip composition failed for reel %d: %s — falling back to single-clip", reel_id, e)

    # Fallback: single-clip composition
    stock_video = _pick_stock_video(reel.get("category", ""), subject_category, used_clips)
    if not stock_video:
        return None

    try:
        video_path = compose_reel_video(
            reel_id=reel_id,
            title=reel.get("title", ""),
            summary=reel.get("summary", ""),
            stock_video_path=stock_video,
            tts_audio_path=str(tts_path) if tts_path else None,
            category=reel.get("category"),
        )
        conn = get_db()
        conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
        conn.commit()
        conn.close()
        log.info("Composed single-clip video for reel %d: %s", reel_id, video_path)
        return video_path
    except Exception as e:
        log.warning("Video composition failed for reel %d: %s", reel_id, e)
        return None


def _run_pipeline(upload_id: int, filepath: str, user_id: int = 1):
    try:
        # Step 0: Fetch user preferences for personalized generation
        prefs = _get_user_prefs(user_id)

        # Step 1: Parse document
        _update_progress(upload_id, 5, "parsing")
        try:
            pages = parse_document(filepath)
        except EmptyDocumentError as e:
            log.warning("Empty document for upload %s: %s", upload_id, e)
            _update_status(upload_id, "error", str(e))
            return
        except ScannedPDFError as e:
            log.warning("Scanned PDF for upload %s: %s", upload_id, e)
            _update_status(upload_id, "error", str(e))
            return

        if not pages:
            _update_status(upload_id, "error", "Document has no extractable text")
            return

        _update_pages(upload_id, len(pages))

        # Build page chunks (3 pages each) for incremental processing
        chunks = []
        for start in range(0, len(pages), PAGES_PER_CHUNK):
            chunk_pages = pages[start:start + PAGES_PER_CHUNK]
            chunk_text = "\n".join(p["text"] for p in chunk_pages)
            if len(chunk_text.strip()) >= 100:
                chunks.append((start, chunk_pages, chunk_text))

        if not chunks:
            _update_status(upload_id, "error", "Document has no extractable text")
            return

        total_chunks = len(chunks)
        full_text = "\n".join(p["text"] for p in pages)

        # Step 2: Detect doc type + subject category from first chunk (fast)
        _update_progress(upload_id, 15, "analyzing")
        first_chunk_text = chunks[0][2]
        doc_type = detect_doc_type(first_chunk_text)
        _update_doc_type(upload_id, doc_type)

        subject_category = detect_subject_category(first_chunk_text)
        _update_subject_category(upload_id, subject_category)

        # Step 3: Process chunks — single LLM call per chunk, stream reels to frontend
        _update_progress(upload_id, 20, "generating")

        chunks_completed = 0
        chunks_failed = 0
        ollama_down = False
        used_clips = set()  # Track clips used across reels to avoid repetition

        for ci, (start_page, chunk_pages, chunk_text) in enumerate(chunks):
            chunk_progress = 20 + int(((ci + 1) / total_chunks) * 50)
            _update_progress(upload_id, chunk_progress, "generating")

            page_range = f"{start_page + 1}-{start_page + len(chunk_pages)}"
            log.info("Upload %s: chunk %d/%d (pages %s, %d chars)",
                     upload_id, ci + 1, total_chunks, page_range, len(chunk_text))

            # Single LLM call — generate reels directly from chunk text
            topic_label = f"Key Concepts (pages {page_range})"
            try:
                result = generate_topic_reel(topic_label, chunk_text, doc_type, prefs)
            except OllamaUnavailableError:
                log.error("Ollama went down at chunk %d/%d for upload %s", ci + 1, total_chunks, upload_id)
                ollama_down = True
                break
            except httpx.TimeoutException:
                log.warning("Ollama timed out on chunk %d for upload %s, skipping", ci + 1, upload_id)
                chunks_failed += 1
                continue
            except Exception:
                log.exception("Error generating reel for chunk %d, upload %s", ci + 1, upload_id)
                chunks_failed += 1
                continue

            topic_reels = result.get("reels", [])
            bg_paths = assign_images(topic_reels, subject_category)
            saved_reels = []
            for reel, bg_image in zip(topic_reels, bg_paths):
                reel_id = _save_reel(upload_id, reel, start_page + 1, bg_image, source_text=chunk_text)
                saved_reels.append((reel_id, reel, bg_image))

            for fc in result.get("flashcards", []):
                _save_flashcard(upload_id, fc)

            # Video composition — notify frontend only after video is ready
            _update_progress(upload_id, chunk_progress + 2, "composing")
            for reel_id, reel, bg_image in saved_reels:
                video_path = _try_compose_video(reel_id, reel, subject_category, used_clips)
                _notify_new_reel(upload_id, reel_id, reel, bg_image, page_ref=start_page + 1, video_path=video_path)

            if topic_reels:
                chunks_completed += 1
            else:
                chunks_failed += 1

        # Handle failures
        if ollama_down:
            if chunks_completed > 0:
                _update_status(
                    upload_id, "partial",
                    f"Generated reels from {chunks_completed}/{total_chunks} sections before Ollama became unavailable. "
                    "Partial reels are available. Re-upload to retry.",
                )
                _update_progress(upload_id, 70, "partial")
            else:
                _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            return

        if chunks_failed and chunks_completed > 0:
            log.info("Upload %s: %d/%d chunks succeeded", upload_id, chunks_completed, total_chunks)
            _update_status(
                upload_id, "partial",
                f"Generated reels from {chunks_completed}/{total_chunks} sections. "
                f"{chunks_failed} sections failed and were skipped.",
            )
        elif chunks_failed and chunks_completed == 0:
            _update_status(upload_id, "error", "All sections failed to generate reels. Please try again later.")
            return

        # Step 4: Generate document-level summary (reels already visible to user)
        _update_progress(upload_id, 72, "summarizing")
        doc_summary = generate_doc_summary(full_text)
        if doc_summary:
            _save_doc_summary(upload_id, doc_summary)
            log.info("Upload %s: doc summary generated (%d chars)", upload_id, len(doc_summary))
        else:
            log.warning("Upload %s: doc summary generation failed or skipped", upload_id)

        # Step 5: Embed chunks for RAG / Chat Q&A
        _update_progress(upload_id, 80, "embedding")
        try:
            asyncio.run(embed_chunks(upload_id, full_text, lambda p: _update_progress(upload_id, 80 + int(p * 18), "embedding")))
            _set_qa_ready(upload_id)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            log.error("Embedding failed for upload %s: %s", upload_id, e)
            _update_status(
                upload_id, "partial",
                "Reels generated but chat Q&A is unavailable — embedding failed. "
                "Reels are still viewable.",
            )
            _update_progress(upload_id, 95, "partial")
            return

        _update_progress(upload_id, 100, "done")
        _update_status(upload_id, "done")

    except Exception as e:
        log.exception("Pipeline error for upload %s", upload_id)
        _update_status(upload_id, "error", f"Unexpected error: {type(e).__name__}")

    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass


def _notify_progress(upload_id: int, progress: int, stage: str, status: str | None = None, error: str | None = None):
    """Push a progress update to any WebSocket subscribers (non-blocking from thread)."""
    loop = _event_loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_upload_progress(upload_id, progress, stage, status, error),
            loop,
        )
    except Exception:
        log.debug("WS notify failed for upload %s", upload_id)


def _notify_new_reel(upload_id: int, reel_id: int, reel: dict, bg_image: str | None, page_ref: int, video_path: str | None = None):
    """Push a newly-saved reel to frontend for real-time feed streaming."""
    loop = _event_loop
    if loop is None or loop.is_closed():
        return
    reel_data = {
        "id": reel_id,
        "upload_id": upload_id,
        "title": reel.get("title", ""),
        "summary": reel.get("summary", ""),
        "narration": reel.get("narration", ""),
        "category": reel.get("category", ""),
        "keywords": reel.get("keywords", ""),
        "page_ref": page_ref,
        "bg_image": bg_image,
        "video_path": video_path,
    }
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_new_reel(upload_id, reel_data),
            loop,
        )
    except Exception:
        log.debug("WS new_reel notify failed for upload %s reel %s", upload_id, reel_id)


def _update_progress(upload_id: int, progress: int, stage: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET progress = ?, stage = ? WHERE id = ?", (progress, stage, upload_id))
    conn.commit()
    conn.close()
    _notify_progress(upload_id, progress, stage)


def _update_status(upload_id: int, status: str, error_message: str = None):
    conn = get_db()
    conn.execute(
        "UPDATE uploads SET status = ?, error_message = ? WHERE id = ?",
        (status, error_message, upload_id),
    )
    conn.commit()
    conn.close()
    _notify_progress(upload_id, 0, "", status, error_message)


def _update_pages(upload_id: int, total_pages: int):
    conn = get_db()
    conn.execute("UPDATE uploads SET total_pages = ? WHERE id = ?", (total_pages, upload_id))
    conn.commit()
    conn.close()


def _set_qa_ready(upload_id: int):
    conn = get_db()
    conn.execute("UPDATE uploads SET qa_ready = 1 WHERE id = ?", (upload_id,))
    conn.commit()
    conn.close()


def _update_doc_type(upload_id: int, doc_type: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET doc_type = ? WHERE id = ?", (doc_type, upload_id))
    conn.commit()
    conn.close()


def _update_subject_category(upload_id: int, subject_category: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET subject_category = ? WHERE id = ?", (subject_category, upload_id))
    conn.commit()
    conn.close()


def _save_reel(upload_id: int, reel: dict, page_ref: int, bg_image: str = None, source_text: str = "") -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO reels (upload_id, title, summary, narration, category, keywords, page_ref, bg_image, source_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, reel.get("title", ""), reel.get("summary", ""), reel.get("narration", ""), reel.get("category", ""), reel.get("keywords", ""), page_ref, bg_image, (source_text or "")[:5000]),
    )
    conn.commit()
    reel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return reel_id


def _save_flashcard(upload_id: int, fc: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO flashcards (upload_id, question, answer) VALUES (?, ?, ?)",
        (upload_id, fc.get("question", ""), fc.get("answer", "")),
    )
    conn.commit()
    conn.close()


def _save_doc_summary(upload_id: int, summary: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET doc_summary = ? WHERE id = ?", (summary, upload_id))
    conn.commit()
    conn.close()
