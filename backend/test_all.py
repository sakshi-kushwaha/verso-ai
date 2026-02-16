import asyncio
import numpy as np

# ── Test 1: Chunking ──────────────────────────────────────────────
print("=" * 50)
print("TEST 1: Chunking")
print("=" * 50)

from rag.embedder import chunk_text

# Short text → single chunk
chunks = chunk_text("Hello world. This is a test.")
assert len(chunks) == 1
print(f"  Short text: {len(chunks)} chunk ✓")

# Long text → multiple chunks
long_text = "This is a sentence. " * 40  # ~800 chars
chunks = chunk_text(long_text)
assert all(len(c) <= 500 for c in chunks)
print(f"  Long text: {len(chunks)} chunks, all ≤500 chars ✓")

# Empty text
assert chunk_text("") == []
assert chunk_text("   ") == []
print("  Empty text: returns [] ✓")

print("PASSED ✓\n")


# ── Test 2: Store (save/load roundtrip) ───────────────────────────
print("=" * 50)
print("TEST 2: Store (save/load)")
print("=" * 50)

from rag.store import save_embeddings, load_embeddings, delete_embeddings

chunks = ["chunk one", "chunk two", "chunk three"]
vectors = np.random.randn(3, 768).astype(np.float32)
save_embeddings(upload_id=9999, chunks=chunks, vectors=vectors)

result = load_embeddings(upload_id=9999)
assert result is not None
loaded_chunks, loaded_vectors = result
assert loaded_chunks == chunks
assert np.allclose(loaded_vectors, vectors)
print(f"  Saved & loaded {len(chunks)} chunks, shape {loaded_vectors.shape} ✓")

delete_embeddings(upload_id=9999)
assert load_embeddings(upload_id=9999) is None
print("  Delete & verify gone ✓")

print("PASSED ✓\n")


# ── Test 3: Embedding via Ollama ──────────────────────────────────
print("=" * 50)
print("TEST 3: Embedding (Ollama)")
print("=" * 50)

from rag.embedder import embed_text

async def test_embed():
    vec = await embed_text("What is machine learning?")
    assert isinstance(vec, list)
    assert len(vec) == 768
    print(f"  Vector dimension: {len(vec)} ✓")
    print(f"  First 5 values: {[round(v, 4) for v in vec[:5]]}")

asyncio.run(test_embed())
print("PASSED ✓\n")


# ── Test 4: Full RAG Pipeline ─────────────────────────────────────
print("=" * 50)
print("TEST 4: Full RAG Pipeline")
print("=" * 50)

from rag.embedder import embed_chunks
from rag.retriever import retrieve_chunks

SAMPLE_TEXT = """
Machine learning is a subset of artificial intelligence that focuses on
building systems that learn from data. Deep learning is a subset of machine
learning that uses neural networks with many layers. Natural language
processing deals with the interaction between computers and human language.
Computer vision enables machines to interpret visual information from the
world. Reinforcement learning trains agents to make sequences of decisions
by rewarding desired behaviors.
"""

async def test_rag():
    count = await embed_chunks(upload_id=8888, full_text=SAMPLE_TEXT)
    print(f"  Embedded {count} chunks ✓")

    results = await retrieve_chunks("What is deep learning?", upload_id=8888)
    print(f"  Retrieved top {len(results)} results:")
    for r in results:
        print(f"    score={r['score']:.3f} | {r['chunk'][:70]}...")

    assert len(results) > 0
    assert results[0]["score"] >= results[-1]["score"]
    print("  Results sorted by descending score ✓")

    # cleanup
    delete_embeddings(upload_id=8888)

asyncio.run(test_rag())
print("PASSED ✓\n")


# ── Test 5: TTS ───────────────────────────────────────────────────
print("=" * 50)
print("TEST 5: TTS (espeak-ng)")
print("=" * 50)

from tts.engine import generate_audio, get_audio_path

text = "This is a test of the Verso text to speech system."
path = generate_audio(text)
assert path.exists()
size = path.stat().st_size
print(f"  Generated: {path.name} ({size} bytes) ✓")

# Cache hit
path2 = generate_audio(text)
assert path == path2
print("  Cache hit returns same path ✓")

# Cache detection
assert get_audio_path(text) is not None
assert get_audio_path("never generated") is None
print("  Cache detection works ✓")

# Cleanup
path.unlink()
print("PASSED ✓\n")


print("=" * 50)
print("ALL TESTS PASSED ✓")
print("=" * 50)
