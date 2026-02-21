import logging
import os
import random
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from database import get_db
import httpx
from parser import parse_document, EmptyDocumentError, ScannedPDFError
from llm import (
    detect_doc_type, detect_subject_category, detect_doc_classification,
    generate_doc_summary,
    generate_reels, generate_reel_script,
    extract_topics, gather_topic_content, generate_topic_reel,
    generate_topic_reel_with_clips,
    OllamaUnavailableError,
)
from bg_images import assign_images, _resolve_category
from rag import embed_chunks
from video import compose_reel_video, compose_multi_clip_reel, get_clips_for_category
from tts.engine import generate_audio
from config import STOCK_VIDEOS_DIR
from ws_manager import manager

log = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
BATCH_SIZE = 3

# Thread pool for overlapping TTS+ffmpeg with LLM calls
_video_executor = ThreadPoolExecutor(max_workers=1)

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


def _pick_stock_video(reel_category: str, upload_category: str) -> str | None:
    """Pick a random stock video matching the reel's category."""
    cat = _resolve_category(reel_category, upload_category)
    folder = STOCK_VIDEOS_DIR / cat
    if not folder.is_dir():
        folder = STOCK_VIDEOS_DIR / "general"
    if not folder.is_dir():
        return None
    videos = [f for f in folder.iterdir() if f.suffix.lower() == ".mp4"]
    if not videos:
        return None
    return str(random.choice(videos))


def _try_compose_video(reel_id: int, reel: dict, subject_category: str):
    """Try to compose a video for a reel. Tries multi-clip first, falls back to single-clip."""
    cat = _resolve_category(reel.get("category", ""), subject_category)

    # Generate TTS from narration — voice rotates by reel_id for variety
    tts_path = None
    narration = reel.get("narration", reel.get("summary", ""))
    if narration:
        # Strip markdown formatting so TTS doesn't read "asterisk" etc.
        import re
        narration = re.sub(r'\*+', '', narration).strip()
        try:
            tts_path = generate_audio(narration, reel_index=reel_id)
        except Exception:
            log.debug("TTS failed for reel %d, composing without narration", reel_id)

    # Try multi-clip composition first
    try:
        clips = get_clips_for_category(cat)
        if clips and len(clips) >= 2:
            script = generate_reel_script(
                text=reel.get("summary", ""),
                category=cat,
                clips=clips,
                narration=narration or "",
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
                conn = get_db()
                conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
                conn.commit()
                conn.close()
                log.info("Composed multi-clip video for reel %d: %s", reel_id, video_path)
                return
    except Exception as e:
        log.warning("Multi-clip composition failed for reel %d: %s — falling back to single-clip", reel_id, e)

    # Fallback: single-clip composition
    stock_video = _pick_stock_video(reel.get("category", ""), subject_category)
    if not stock_video:
        return

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
    except Exception as e:
        log.warning("Video composition failed for reel %d: %s", reel_id, e)


def _compose_and_notify(upload_id: int, reel_id: int, reel: dict, subject_category: str,
                        segments: list[dict] | None = None):
    """Run video composition + WS notification in the thread pool.

    If segments are provided (from merged LLM call), use them directly for
    multi-clip composition without an extra LLM call.
    """
    if segments:
        _try_compose_video_with_segments(reel_id, reel, subject_category, segments)
    else:
        _try_compose_video(reel_id, reel, subject_category)
    _notify_reel_ready(upload_id, reel_id)


def _try_compose_video_with_segments(reel_id: int, reel: dict, subject_category: str,
                                      segments: list[dict]):
    """Compose multi-clip video using pre-selected segments (no extra LLM call)."""
    cat = _resolve_category(reel.get("category", ""), subject_category)

    # Generate TTS
    tts_path = None
    narration = reel.get("narration", reel.get("summary", ""))
    if narration:
        try:
            tts_path = generate_audio(narration, reel_index=reel_id)
        except Exception:
            log.debug("TTS failed for reel %d, composing without narration", reel_id)

    # Validate segments against available clips
    clips = get_clips_for_category(cat)
    valid_filenames = {c["file"] for c in clips}
    validated = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        clip_file = seg.get("clip", "")
        if clip_file not in valid_filenames:
            continue
        dur = seg.get("duration", 5)
        if not isinstance(dur, (int, float)) or dur < 2:
            dur = 5
        validated.append({
            "clip": clip_file,
            "overlay": str(seg.get("overlay", ""))[:60],
            "duration": float(dur),
        })

    if len(validated) >= 2:
        try:
            video_path = compose_multi_clip_reel(
                reel_id=reel_id,
                title=reel.get("title", ""),
                narration=narration or "",
                segments=validated,
                category=cat,
                tts_audio_path=str(tts_path) if tts_path else None,
            )
            conn = get_db()
            conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
            conn.commit()
            conn.close()
            log.info("Composed multi-clip video for reel %d (merged): %s", reel_id, video_path)
            return
        except Exception as e:
            log.warning("Multi-clip composition failed for reel %d: %s — falling back", reel_id, e)

    # Fallback to single-clip
    stock_video = _pick_stock_video(reel.get("category", ""), subject_category)
    if not stock_video:
        return
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
        log.info("Composed single-clip fallback video for reel %d: %s", reel_id, video_path)
    except Exception as e:
        log.warning("Video composition failed for reel %d: %s", reel_id, e)


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

        # Step 2: Detect doc type + subject category in ONE LLM call
        _update_progress(upload_id, 15, "analyzing")
        full_text = "\n".join(p["text"] for p in pages)
        doc_type, subject_category = detect_doc_classification(full_text)
        _update_doc_type(upload_id, doc_type)
        _update_subject_category(upload_id, subject_category)

        # Step 3: Extract topics (summary deferred until after reels)
        _update_progress(upload_id, 20, "extracting")

        # Decide number of reels based on document length
        num_topics = min(max(3, len(pages) // 3), 15)

        try:
            topics = extract_topics(full_text, num_topics=num_topics)
        except OllamaUnavailableError:
            _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            return

        if not topics:
            # Fallback: treat the whole document as one topic
            topics = [{"topic": "Key Concepts", "keywords": subject_category}]

        log.info("Upload %s: extracted %d topics — %s",
                 upload_id, len(topics), ", ".join(t["topic"] for t in topics))

        # Pre-fetch clips for the subject category (used by merged LLM call)
        cat = _resolve_category(subject_category, subject_category)
        available_clips = get_clips_for_category(cat)

        reels_completed = 0
        reels_failed = 0
        ollama_down = False
        pending_futures = []

        for i, topic in enumerate(topics):
            topic_progress = 20 + int(((i + 1) / len(topics)) * 50)
            _update_progress(upload_id, topic_progress, "generating")

            # Gather relevant content for this topic
            topic_text = gather_topic_content(topic, full_text)
            log.info("Topic %d/%d: %r (%d chars)", i + 1, len(topics), topic["topic"], len(topic_text))

            # Single merged LLM call: generates reel content + picks clips
            try:
                if available_clips and len(available_clips) >= 2:
                    result = generate_topic_reel_with_clips(
                        topic["topic"], topic_text, doc_type, prefs,
                        category=subject_category, clips=available_clips,
                    )
                else:
                    result = generate_topic_reel(topic["topic"], topic_text, doc_type, prefs, category=subject_category)
            except OllamaUnavailableError:
                log.error("Ollama went down at topic %d/%d for upload %s", i + 1, len(topics), upload_id)
                ollama_down = True
                break
            except httpx.TimeoutException:
                log.warning("Ollama timed out on topic %r for upload %s, skipping", topic["topic"], upload_id)
                reels_failed += 1
                continue
            except Exception:
                log.exception("Error generating reel for topic %r, upload %s", topic["topic"], upload_id)
                reels_failed += 1
                continue

            topic_reels = result.get("reels", [])
            bg_paths = assign_images(topic_reels, subject_category)
            saved_reels = []
            for reel, bg_image in zip(topic_reels, bg_paths):
                reel_id = _save_reel(upload_id, reel, i + 1, bg_image, source_text=topic_text)
                saved_reels.append((reel_id, reel))

            for fc in result.get("flashcards", []):
                _save_flashcard(upload_id, fc)

            # Submit video composition to thread pool (overlaps with next LLM call)
            _update_progress(upload_id, topic_progress + 2, "composing")
            for reel_id, reel in saved_reels:
                segments = reel.get("segments")
                fut = _video_executor.submit(
                    _compose_and_notify, upload_id, reel_id, reel, subject_category, segments,
                )
                pending_futures.append(fut)

            reels_completed += 1

        # Wait for all video composition futures to finish
        for fut in pending_futures:
            try:
                fut.result(timeout=300)
            except Exception as e:
                log.warning("Video future failed: %s", e)

        # Handle failures
        if ollama_down:
            if reels_completed > 0:
                _update_status(
                    upload_id, "partial",
                    f"Generated {reels_completed}/{len(topics)} reels before Ollama became unavailable. "
                    "Partial reels are available. Re-upload to retry.",
                )
                _update_progress(upload_id, 70, "partial")
            else:
                _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            return

        if reels_failed and reels_completed > 0:
            log.info("Upload %s: %d/%d topics succeeded", upload_id, reels_completed, len(topics))
            _update_status(
                upload_id, "partial",
                f"Generated {reels_completed}/{len(topics)} reels. "
                f"{reels_failed} topics failed and were skipped.",
            )
        elif reels_failed and reels_completed == 0:
            _update_status(upload_id, "error", "All topic reels failed. Please try again later.")
            return

        # Step 4: Mark as done immediately, defer embedding + summary
        _update_progress(upload_id, 95, "done")
        _update_status(upload_id, "done")

        # Deferred: doc summary + embedding in background
        def _deferred_tasks():
            try:
                # Generate doc summary (deferred from before reel loop)
                _update_progress(upload_id, 96, "summarizing")
                doc_summary = generate_doc_summary(full_text)
                if doc_summary:
                    _save_doc_summary(upload_id, doc_summary)
                    log.info("Upload %s: deferred doc summary generated (%d chars)", upload_id, len(doc_summary))
            except Exception as e:
                log.warning("Deferred doc summary failed for upload %s: %s", upload_id, e)

            try:
                _update_progress(upload_id, 97, "embedding")
                asyncio.run(embed_chunks(upload_id, full_text, lambda p: None))
                _set_qa_ready(upload_id)
                _update_progress(upload_id, 100, "done")
                log.info("Upload %s: deferred embedding complete, Q&A ready", upload_id)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                log.error("Deferred embedding failed for upload %s: %s", upload_id, e)

        threading.Thread(target=_deferred_tasks, daemon=True).start()

    except Exception as e:
        log.exception("Pipeline error for upload %s", upload_id)
        _update_status(upload_id, "error", f"Unexpected error: {type(e).__name__}")

    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass


def _notify_reel_ready(upload_id: int, reel_id: int):
    """Push a reel_ready event to WebSocket subscribers so the frontend can show it immediately."""
    loop = _event_loop
    if loop is None or loop.is_closed():
        return
    conn = get_db()
    row = conn.execute("SELECT * FROM reels WHERE id = ?", (reel_id,)).fetchone()
    conn.close()
    if not row:
        return
    reel_data = dict(row)
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_reel_ready(upload_id, reel_data),
            loop,
        )
    except Exception:
        log.debug("WS reel_ready failed for upload %s reel %s", upload_id, reel_id)


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
        "INSERT INTO reels (upload_id, title, summary, narration, one_liner, category, keywords, page_ref, bg_image, source_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, reel.get("title", ""), reel.get("summary", ""), reel.get("narration", ""), reel.get("one_liner", ""), reel.get("category", ""), reel.get("keywords", ""), page_ref, bg_image, (source_text or "")[:5000]),
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
