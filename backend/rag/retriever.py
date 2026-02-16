import numpy as np
from config import TOP_K
from rag.embedder import embed_text
from rag.store import load_embeddings


async def retrieve_chunks(question: str, upload_id: int) -> list[dict]:
    q_vec = np.array(await embed_text(question), dtype=np.float32)

    result = load_embeddings(upload_id)
    if result is None:
        raise ValueError(f"No embeddings found for upload_id={upload_id}")
    chunks, vectors = result

    # Cosine similarity
    q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-10)
    v_norms = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10)
    similarities = v_norms @ q_norm

    k = min(TOP_K, len(chunks))
    top_indices = np.argsort(similarities)[::-1][:k]

    return [
        {
            "chunk": chunks[i],
            "score": float(similarities[i]),
            "index": int(i),
        }
        for i in top_indices
    ]
