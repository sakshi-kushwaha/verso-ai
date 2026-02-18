import logging
import os
import random
import asyncio
import threading
from database import get_db
import httpx
from parser import parse_document, detect_chapters, EmptyDocumentError, ScannedPDFError
from llm import detect_doc_type, detect_subject_category, generate_reels, generate_reel_script, OllamaUnavailableError
from bg_images import assign_images, _resolve_category
from rag import embed_chunks
from video import compose_reel_video, compose_multi_clip_reel, get_clips_for_category
from tts.engine import generate_audio
from config import STOCK_VIDEOS_DIR
from ws_manager import manager

log = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
BATCH_SIZE = 3

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

    # Generate TTS from narration
    tts_path = None
    narration = reel.get("narration", reel.get("summary", ""))
    if narration:
        try:
            tts_path = generate_audio(narration)
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

        # Step 2: Detect doc type from first page text
        _update_progress(upload_id, 15, "analyzing")
        full_text = "\n".join(p["text"] for p in pages)
        doc_type = detect_doc_type(full_text)
        _update_doc_type(upload_id, doc_type)

        # Step 2b: Detect subject category for background images
        subject_category = detect_subject_category(full_text)
        _update_subject_category(upload_id, subject_category)

        # Step 3: Detect chapters and generate reels
        _update_progress(upload_id, 20, "extracting")
        sections = detect_chapters(pages)
        max_sections = max(2, len(pages) // 2)
        sections = sections[:max_sections]

        total_batches = max(1, (len(sections) + BATCH_SIZE - 1) // BATCH_SIZE)
        batches_completed = 0
        failed_batches = []
        ollama_down = False

        for i in range(0, len(sections), BATCH_SIZE):
            batch_num = i // BATCH_SIZE
            batch_progress = 20 + int((batch_num / total_batches) * 50)
            _update_progress(upload_id, batch_progress, "generating")

            batch = sections[i:i + BATCH_SIZE]
            batch_text = "\n".join(s["text"] for s in batch)

            try:
                result = generate_reels(batch_text, doc_type, prefs)
            except OllamaUnavailableError:
                log.error("Ollama went down during batch %d/%d for upload %s", batch_num + 1, total_batches, upload_id)
                ollama_down = True
                break
            except httpx.TimeoutException:
                log.warning("Ollama timed out on batch %d/%d for upload %s, skipping", batch_num + 1, total_batches, upload_id)
                failed_batches.append(batch_num + 1)
                continue
            except Exception:
                log.exception("Unexpected error on batch %d/%d for upload %s, skipping", batch_num + 1, total_batches, upload_id)
                failed_batches.append(batch_num + 1)
                continue

            batch_reels = result.get("reels", [])
            bg_paths = assign_images(batch_reels, subject_category)
            saved_reels = []
            for reel, bg_image in zip(batch_reels, bg_paths):
                reel_id = _save_reel(upload_id, reel, batch[0].get("start_page", i + 1), bg_image)
                saved_reels.append((reel_id, reel))

            for fc in result.get("flashcards", []):
                _save_flashcard(upload_id, fc)

            # Video composition — try to compose video for each reel
            _update_progress(upload_id, batch_progress + 2, "composing")
            for reel_id, reel in saved_reels:
                _try_compose_video(reel_id, reel, subject_category)

            batches_completed += 1

        # If Ollama server is completely down, save partial or error
        if ollama_down:
            if batches_completed > 0:
                log.info("Saving %d/%d partial batches for upload %s", batches_completed, total_batches, upload_id)
                _update_status(
                    upload_id, "partial",
                    f"Generated {batches_completed}/{total_batches} batches before Ollama became unavailable. "
                    "Partial reels are available. Re-upload to retry.",
                )
                _update_progress(upload_id, 70, "partial")
            else:
                _update_status(upload_id, "error", "Ollama is unavailable. Please try again later.")
            return

        # If some batches failed but others succeeded, mark as partial and continue
        if failed_batches and batches_completed > 0:
            skipped = ", ".join(str(b) for b in failed_batches)
            log.info("Upload %s: %d batches succeeded, batches %s failed", upload_id, batches_completed, skipped)
            _update_status(
                upload_id, "partial",
                f"Generated {batches_completed}/{total_batches} batches. "
                f"Batches {skipped} timed out and were skipped. Partial reels are available.",
            )
        elif failed_batches and batches_completed == 0:
            _update_status(upload_id, "error", "All batches failed. Please try again later.")
            return

        # Step 4: Embed chunks for RAG / Chat Q&A
        _update_progress(upload_id, 70, "embedding")
        try:
            asyncio.run(embed_chunks(upload_id, full_text, lambda p: _update_progress(upload_id, 70 + int(p * 25), "embedding")))
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


def _save_reel(upload_id: int, reel: dict, page_ref: int, bg_image: str = None) -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO reels (upload_id, title, summary, narration, category, keywords, page_ref, bg_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, reel.get("title", ""), reel.get("summary", ""), reel.get("narration", ""), reel.get("category", ""), reel.get("keywords", ""), page_ref, bg_image),
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
