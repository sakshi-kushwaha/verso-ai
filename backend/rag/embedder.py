import re
import httpx
import numpy as np
from config import (
    OLLAMA_HOST,
    EMBED_MODEL,
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP_CHARS,
    OLLAMA_EMBED_TIMEOUT,
)
from rag.store import save_embeddings


def chunk_text(full_text: str) -> list[str]:
    text = re.sub(r"\s+", " ", full_text).strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        # If single sentence exceeds max, hard-split at word boundaries
        if len(sentence) > CHUNK_MAX_CHARS:
            if current:
                chunks.append(current.strip())
                current = ""
            words = sentence.split()
            part = ""
            for word in words:
                if len(part) + len(word) + 1 <= CHUNK_MAX_CHARS:
                    part = f"{part} {word}" if part else word
                else:
                    if part:
                        chunks.append(part.strip())
                    part = word
            if part:
                chunks.append(part.strip())
            continue

        if len(current) + len(sentence) + 1 <= CHUNK_MAX_CHARS:
            current = f"{current} {sentence}" if current else sentence
        else:
            chunks.append(current.strip())
            # Start new chunk with overlap from previous
            overlap = current[-CHUNK_OVERLAP_CHARS:] if len(current) > CHUNK_OVERLAP_CHARS else ""
            current = f"{overlap} {sentence}".strip() if overlap else sentence

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]


async def embed_text(text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_HOST}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=OLLAMA_EMBED_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]


async def embed_chunks(upload_id: int, full_text: str) -> int:
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    vectors = []
    for chunk in chunks:
        vec = await embed_text(chunk)
        vectors.append(vec)

    vectors_np = np.array(vectors, dtype=np.float32)
    save_embeddings(upload_id, chunks, vectors_np)
    return len(chunks)
