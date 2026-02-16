import os
import threading
from database import get_db
from parser import parse_document, detect_chapters
from llm import detect_doc_type, generate_reels

TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "temp")
BATCH_SIZE = 5


def process_upload(upload_id: int, filepath: str):
    thread = threading.Thread(target=_run_pipeline, args=(upload_id, filepath), daemon=True)
    thread.start()


def _run_pipeline(upload_id: int, filepath: str):
    try:
        pages = parse_document(filepath)
        if not pages:
            _update_status(upload_id, "error")
            return

        _update_pages(upload_id, len(pages))

        full_text = "\n".join(p["text"] for p in pages)
        doc_type = detect_doc_type(full_text)
        _update_doc_type(upload_id, doc_type)

        sections = detect_chapters(pages)
        max_sections = max(1, len(pages) // 4)
        sections = sections[:max_sections]

        for i in range(0, len(sections), BATCH_SIZE):
            batch = sections[i:i + BATCH_SIZE]
            batch_text = "\n".join(s["text"] for s in batch)

            result = generate_reels(batch_text, doc_type)

            for reel in result.get("reels", []):
                _save_reel(upload_id, reel, batch[0].get("start_page", i + 1))

            for fc in result.get("flashcards", []):
                _save_flashcard(upload_id, fc)

        _update_status(upload_id, "done")

    except Exception as e:
        print(f"Pipeline error for upload {upload_id}: {e}")
        _update_status(upload_id, "error")

    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass


def _update_status(upload_id: int, status: str):
    conn = get_db()
    conn.execute("UPDATE uploads SET status = ? WHERE id = ?", (status, upload_id))
    conn.commit()
    conn.close()


def _update_pages(upload_id: int, total_pages: int):
    conn = get_db()
    conn.execute("UPDATE uploads SET total_pages = ? WHERE id = ?", (total_pages, upload_id))
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
