import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from database import get_db
from pipeline import process_upload, TEMP_DIR

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF and DOCX files are supported")

    os.makedirs(TEMP_DIR, exist_ok=True)
    temp_path = os.path.join(TEMP_DIR, file.filename)

    size = 0
    with open(temp_path, "wb") as f:
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                os.unlink(temp_path)
                raise HTTPException(400, "File exceeds 50 MB limit")
            f.write(chunk)

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO uploads (filename, status) VALUES (?, 'processing')",
        (file.filename,),
    )
    upload_id = cursor.lastrowid
    conn.commit()
    conn.close()

    process_upload(upload_id, temp_path)

    return {"id": upload_id, "filename": file.filename, "status": "processing"}


@router.get("/uploads")
def list_uploads():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, status, qa_ready FROM uploads ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/upload/status/{upload_id}")
def get_upload_status(upload_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Upload not found")

    reels_count = conn.execute(
        "SELECT COUNT(*) FROM reels WHERE upload_id = ?", (upload_id,)
    ).fetchone()[0]

    conn.close()

    return {
        "id": row["id"],
        "filename": row["filename"],
        "status": row["status"],
        "doc_type": row["doc_type"],
        "total_pages": row["total_pages"],
        "reels_generated": reels_count,
        "qa_ready": bool(row["qa_ready"]),
    }
