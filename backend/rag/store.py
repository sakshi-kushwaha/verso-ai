import json
import numpy as np
from config import EMBEDDINGS_DIR


def save_embeddings(upload_id: int, chunks: list[str], vectors: np.ndarray) -> None:
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    vec_path = EMBEDDINGS_DIR / f"{upload_id}_vectors.npy"
    chunk_path = EMBEDDINGS_DIR / f"{upload_id}_chunks.json"
    np.save(str(vec_path), vectors)
    with open(chunk_path, "w") as f:
        json.dump(chunks, f)


def load_embeddings(upload_id: int) -> tuple[list[str], np.ndarray] | None:
    vec_path = EMBEDDINGS_DIR / f"{upload_id}_vectors.npy"
    chunk_path = EMBEDDINGS_DIR / f"{upload_id}_chunks.json"
    if not vec_path.exists() or not chunk_path.exists():
        return None
    vectors = np.load(str(vec_path))
    with open(chunk_path, "r") as f:
        chunks = json.load(f)
    return chunks, vectors


def delete_embeddings(upload_id: int) -> None:
    vec_path = EMBEDDINGS_DIR / f"{upload_id}_vectors.npy"
    chunk_path = EMBEDDINGS_DIR / f"{upload_id}_chunks.json"
    vec_path.unlink(missing_ok=True)
    chunk_path.unlink(missing_ok=True)
