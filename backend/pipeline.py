import logging
import os
import asyncio
import threading
from database import get_db
import httpx
from parser import parse_document, detect_chapters, EmptyDocumentError, ScannedPDFError
from llm import detect_doc_type, generate_reels, OllamaUnavailableError
from rag import embed_chunks

log = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
BATCH_SIZE = 5


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

        # Step 3: Detect chapters and generate reels
        _update_progress(upload_id, 20, "extracting")
        sections = detect_chapters(pages)
        max_sections = max(1, len(pages) // 4)
        sections = sections[:max_sections]

        total_batches = max(1, (len(sections) + BATCH_SIZE - 1) // BATCH_SIZE)
        batches_completed = 0
        ollama_failed = False

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
                ollama_failed = True
                break
            except httpx.TimeoutException:
                log.error("Ollama timed out on batch %d/%d for upload %s", batch_num + 1, total_batches, upload_id)
                ollama_failed = True
                break

            for reel in result.get("reels", []):
                _save_reel(upload_id, reel, batch[0].get("start_page", i + 1))

            for fc in result.get("flashcards", []):
                _save_flashcard(upload_id, fc)

            batches_completed += 1

        # If Ollama died mid-batch, save partial results
        if ollama_failed:
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


def _update_progress(upload_id: int, progress: int, stage: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET progress = ?, stage = ? WHERE id = ?", (progress, stage, upload_id))
    conn.commit()
    conn.close()


def _update_status(upload_id: int, status: str, error_message: str = None):
    conn = get_db()
    conn.execute(
        "UPDATE uploads SET status = ?, error_message = ? WHERE id = ?",
        (status, error_message, upload_id),
    )
    conn.commit()
    conn.close()


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


def _save_reel(upload_id: int, reel: dict, page_ref: int):
    conn = get_db()
    conn.execute(
        "INSERT INTO reels (upload_id, title, summary, category, keywords, page_ref) VALUES (?, ?, ?, ?, ?, ?)",
        (upload_id, reel.get("title", ""), reel.get("summary", ""), reel.get("category", ""), reel.get("keywords", ""), page_ref),
    )
    conn.commit()
    conn.close()


def _save_flashcard(upload_id: int, fc: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO flashcards (upload_id, question, answer) VALUES (?, ?, ?)",
        (upload_id, fc.get("question", ""), fc.get("answer", "")),
    )
    conn.commit()
    conn.close()
