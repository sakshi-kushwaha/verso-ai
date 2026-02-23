import logging
import math
import os
import random
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from database import get_db
import httpx
from parser import parse_document, EmptyDocumentError, ScannedPDFError
from llm import (
    detect_doc_type, detect_subject_category, detect_doc_classification,
    generate_doc_summary,
    generate_reels, generate_reel_script,
    extract_topics, gather_topic_content, generate_topic_reel,
    OllamaUnavailableError,
)
from bg_images import assign_images, _resolve_category
from rag import embed_chunks
from video import compose_reel_video, compose_multi_clip_reel, get_clips_for_category
from tts.engine import generate_audio
from config import STOCK_VIDEOS_DIR, PIPELINE_TIMEOUT as _PIPELINE_TIMEOUT
from ws_manager import manager

log = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
BATCH_SIZE = 3
PIPELINE_TIMEOUT = _PIPELINE_TIMEOUT  # from config, default 20 min

# Thread pool for overlapping TTS+ffmpeg with LLM calls
_video_executor = ThreadPoolExecutor(max_workers=1)


# Set by main.py lifespan — the running asyncio event loop
_event_loop: asyncio.AbstractEventLoop | None = None


def process_upload(upload_id: int, filepath: str, user_id: int = 1):
    """Run the full pipeline in a background thread."""
    thread = threading.Thread(target=_run_pipeline, args=(upload_id, filepath, user_id), daemon=True)
    thread.start()


def resume_orphaned_uploads():
    """Resume uploads stuck in 'processing' after a server restart.

    Called once during server startup. For each orphaned upload:
    - If the temp file still exists → restart the pipeline from scratch
    - If reels already exist → mark as partial
    - Otherwise → mark as error
    """
    conn = get_db()
    orphans = conn.execute(
        "SELECT id, filepath, user_id FROM uploads WHERE status = 'processing'"
    ).fetchall()
    if not orphans:
        conn.close()
        return

    for row in orphans:
        uid, filepath, user_id = row["id"], row["filepath"], row["user_id"]
        reel_count = conn.execute("SELECT COUNT(*) FROM reels WHERE upload_id = ?", (uid,)).fetchone()[0]

        if filepath and os.path.exists(filepath):
            # Temp file exists — restart pipeline from scratch
            log.info("Resuming orphaned upload %s from scratch (file: %s)", uid, filepath)
            # Reset progress so frontend sees it restart
            conn.execute(
                "UPDATE uploads SET progress = 0, stage = 'uploading', error_message = NULL WHERE id = ?",
                (uid,),
            )
            # Clean up any partial reels/flashcards from the interrupted run
            conn.execute("DELETE FROM flashcards WHERE upload_id = ?", (uid,))
            conn.execute("DELETE FROM reels WHERE upload_id = ?", (uid,))
            conn.commit()
            process_upload(uid, filepath, user_id or 1)
        elif reel_count > 0:
            log.info("Orphaned upload %s has %d reels, marking as done", uid, reel_count)
            conn.execute(
                "UPDATE uploads SET status = 'done', error_message = NULL WHERE id = ?",
                (uid,),
            )
            conn.commit()
        else:
            log.info("Orphaned upload %s has no file or reels, marking as error", uid)
            conn.execute(
                "UPDATE uploads SET status = 'error', error_message = 'Processing was interrupted. Please re-upload.' WHERE id = ?",
                (uid,),
            )
            conn.commit()

    conn.close()


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


_stock_video_queues: dict[str, list] = {}  # category -> shuffled list of video paths


def _pick_stock_video(reel_category: str, upload_category: str) -> str | None:
    """Pick a stock video matching the reel's category using shuffle-based round-robin."""
    cat = _resolve_category(reel_category, upload_category)
    folder = STOCK_VIDEOS_DIR / cat
    if not folder.is_dir():
        folder = STOCK_VIDEOS_DIR / "general"
    if not folder.is_dir():
        return None
    videos = [f for f in folder.iterdir() if f.suffix.lower() == ".mp4"]
    if not videos:
        return None

    # Refill shuffled queue when empty to ensure variety across reels
    if cat not in _stock_video_queues or not _stock_video_queues[cat]:
        shuffled = videos[:]
        random.shuffle(shuffled)
        _stock_video_queues[cat] = shuffled

    return str(_stock_video_queues[cat].pop())


def _try_compose_video(reel_id: int, reel: dict, subject_category: str):
    """Compose a video for a reel. Picks clips programmatically (no LLM call) then falls back to single-clip."""
    cat = _resolve_category(reel.get("category", ""), subject_category)

    # Generate TTS from narration — voice rotates by reel_id for variety
    tts_path = None
    narration = reel.get("narration", reel.get("summary", ""))
    if narration:
        import re
        narration = re.sub(r'\*+', '', narration).strip()
        try:
            tts_path = generate_audio(narration, reel_index=reel_id)
        except Exception:
            log.debug("TTS failed for reel %d, composing without narration", reel_id)

    # Try multi-clip composition — pick clips programmatically (no LLM needed)
    try:
        clips = get_clips_for_category(cat)
        if clips and len(clips) >= 2:
            random.shuffle(clips)
            num_segments = min(3, len(clips))
            segments = [{"clip": clips[i]["file"], "duration": 5} for i in range(num_segments)]
            video_path = compose_multi_clip_reel(
                reel_id=reel_id,
                title=reel.get("title", ""),
                narration=narration or "",
                segments=segments,
                category=cat,
                tts_audio_path=str(tts_path) if tts_path else None,
            )
            conn = get_db()
            conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
            conn.commit()
            conn.close()
            log.info("Composed multi-clip video for reel %d (auto-picked): %s", reel_id, video_path)
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
            narration=narration,
        )
        conn = get_db()
        conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
        conn.commit()
        conn.close()
        log.info("Composed single-clip video for reel %d: %s", reel_id, video_path)
    except Exception as e:
        log.warning("Video composition failed for reel %d: %s", reel_id, e)


def _compose_video_only(upload_id: int, reel_id: int, reel: dict, subject_category: str,
                        segments: list[dict] | None = None):
    """Run video composition in the thread pool.

    Reel-ready notification is sent earlier (right after DB save) so the
    frontend can display reels in real-time before video compositing finishes.
    After video is composed, a video_ready event is sent so the frontend
    can switch from the image card to the video player.
    """
    if segments:
        _try_compose_video_with_segments(reel_id, reel, subject_category, segments)
    else:
        _try_compose_video(reel_id, reel, subject_category)

    # Notify frontend that video is now available
    conn = get_db()
    row = conn.execute("SELECT video_path FROM reels WHERE id = ?", (reel_id,)).fetchone()
    conn.close()
    if row and row["video_path"]:
        _notify_video_ready(upload_id, reel_id, row["video_path"])


# Keep old name as alias for backward compatibility
_compose_and_notify = _compose_video_only


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
            narration=narration,
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
        pipeline_start = time.monotonic()

        # Reset stock video queues so each upload gets fresh variety
        _stock_video_queues.clear()

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

        # Step 1.5: Quick Ollama health check — fail fast if LLM is unreachable
        _update_progress(upload_id, 10, "checking")
        try:
            httpx.get(f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/tags", timeout=10)
        except Exception:
            log.error("Ollama is unreachable for upload %s", upload_id)
            _update_status(upload_id, "error", "AI service is unavailable. Please try again later.")
            return

        # Step 2: Detect doc type + subject category in ONE LLM call
        _update_progress(upload_id, 15, "analyzing")
        full_text = "\n".join(p["text"] for p in pages)
        doc_type, subject_category = detect_doc_classification(full_text)
        _update_doc_type(upload_id, doc_type)
        _update_subject_category(upload_id, subject_category)

        # Step 3: Extract topics (summary deferred until after reels)
        _update_progress(upload_id, 20, "extracting")

        # Decide number of reels based on document length
        # ~1 reel per 3 pages: 10 pages → 3, 26 pages → 8, 50 pages → 16
        # Each reel takes ~2-3 min on CPU, so keep count practical
        num_topics = min(max(3, int(len(pages) * 0.3)), 100)

        try:
            topics = extract_topics(full_text, num_topics=num_topics)
        except OllamaUnavailableError:
            _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            return
        except Exception:
            log.exception("Topic extraction failed for upload %s, using fallback", upload_id)
            topics = []

        if not topics:
            # Fallback: treat the whole document as one topic
            topics = [{"topic": "Key Concepts", "keywords": subject_category}]

        log.info("Upload %s: extracted %d topics — %s",
                 upload_id, len(topics), ", ".join(t["topic"] for t in topics))

        reels_completed = 0
        reels_failed = 0
        ollama_down = False
        pending_futures = []

        for i, topic in enumerate(topics):
            # Check total pipeline timeout
            elapsed = time.monotonic() - pipeline_start
            if elapsed > PIPELINE_TIMEOUT:
                log.warning("Pipeline timeout after %.0fs at topic %d/%d for upload %s",
                            elapsed, i + 1, len(topics), upload_id)
                break

            topic_progress = 20 + int(((i + 1) / len(topics)) * 50)
            _update_progress(upload_id, topic_progress, "generating")

            # Gather relevant content for this topic (keep short for fast LLM)
            topic_text = gather_topic_content(topic, full_text, max_chars=1500)
            log.info("Topic %d/%d: %r (%d chars)", i + 1, len(topics), topic["topic"], len(topic_text))

            # Use generate_topic_reel (no clip list in prompt = much faster on CPU)
            # Video clips are picked programmatically in _try_compose_video
            try:
                result = generate_topic_reel(
                    topic["topic"], topic_text, doc_type, prefs,
                    category=subject_category,
                )
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

            topic_reels = [r for r in result.get("reels", []) if r.get("title") != "Summary"]
            if not topic_reels:
                log.warning("Topic %r returned no valid reels, skipping", topic["topic"])
                reels_failed += 1
                continue

            bg_paths = assign_images(topic_reels, subject_category)
            saved_reels = []
            for reel, bg_image in zip(topic_reels, bg_paths):
                reel_id = _save_reel(upload_id, reel, i + 1, bg_image, source_text=topic_text[:5000])
                saved_reels.append((reel_id, reel))
                _notify_reel_ready(upload_id, reel_id)

            for fc in result.get("flashcards", []):
                fc_id = _save_flashcard(upload_id, fc)
                _notify_flashcard_ready(upload_id, fc_id, fc)

            # Submit video composition to thread pool (overlaps with next LLM call)
            _update_progress(upload_id, topic_progress + 2, "composing")
            for reel_id, reel in saved_reels:
                fut = _video_executor.submit(
                    _compose_video_only, upload_id, reel_id, reel, subject_category, None,
                )
                pending_futures.append(fut)

            reels_completed += len(topic_reels)

        # Wait for all video composition futures to finish
        for fut in pending_futures:
            try:
                fut.result(timeout=300)
            except Exception as e:
                log.warning("Video future failed: %s", e)

        # Handle failures — only error if zero reels were generated
        if reels_completed == 0:
            if ollama_down:
                _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            else:
                _update_status(upload_id, "error", "All topic reels failed. Please try again later.")
            return

        if reels_failed:
            log.info("Upload %s: %d/%d topics succeeded, %d failed",
                     upload_id, reels_completed, len(topics), reels_failed)

        # Step 4: Mark as done immediately, defer embedding + summary
        _update_progress(upload_id, 95, "done")
        _update_status(upload_id, "done")

        # Deferred: doc summary + embedding in background
        def _deferred_tasks():
            try:
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
        try:
            _update_status(upload_id, "error", f"Unexpected error: {type(e).__name__}")
        except Exception:
            # Last resort: direct DB update if _update_status fails
            try:
                conn = get_db()
                conn.execute(
                    "UPDATE uploads SET status = 'error', error_message = ? WHERE id = ?",
                    (f"Unexpected error: {type(e).__name__}", upload_id),
                )
                conn.commit()
                conn.close()
            except Exception:
                log.error("Failed to update error status for upload %s", upload_id)

    finally:
        # Clear filepath in DB and delete temp file — pipeline completed (success or error)
        try:
            conn = get_db()
            conn.execute("UPDATE uploads SET filepath = NULL WHERE id = ?", (upload_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
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


def _notify_video_ready(upload_id: int, reel_id: int, video_path: str):
    """Push a video_ready event so the frontend can switch from image card to video player."""
    loop = _event_loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_video_ready(upload_id, reel_id, video_path),
            loop,
        )
    except Exception:
        log.debug("WS video_ready failed for upload %s reel %s", upload_id, reel_id)


def _notify_flashcard_ready(upload_id: int, fc_id: int, fc: dict):
    """Push a flashcard_ready event to WebSocket subscribers."""
    loop = _event_loop
    if loop is None or loop.is_closed():
        return
    fc_data = {"id": fc_id, "upload_id": upload_id, "question": fc.get("question", ""), "answer": fc.get("answer", "")}
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_flashcard_ready(upload_id, fc_data),
            loop,
        )
    except Exception:
        log.debug("WS flashcard_ready failed for upload %s fc %s", upload_id, fc_id)


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


def _save_flashcard(upload_id: int, fc: dict) -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO flashcards (upload_id, question, answer) VALUES (?, ?, ?)",
        (upload_id, fc.get("question", ""), fc.get("answer", "")),
    )
    fc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return fc_id


def _save_doc_summary(upload_id: int, summary: str):
    import re
    # Strip markdown headers/formatting that the LLM sometimes adds
    summary = re.sub(r'^#{1,6}\s+.*\n?', '', summary, flags=re.MULTILINE).strip()
    summary = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', summary)  # strip bold/italic
    # Remove "Summary:" or "Summary\n" prefix the LLM echoes from the prompt
    summary = re.sub(r'^summary\s*:?\s*\n*', '', summary, flags=re.IGNORECASE).strip()
    # Collapse 3+ newlines to 2
    summary = re.sub(r'\n{3,}', '\n\n', summary)
    conn = get_db()
    conn.execute("UPDATE uploads SET doc_summary = ? WHERE id = ?", (summary, upload_id))
    conn.commit()
    conn.close()
