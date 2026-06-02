"""
query.py — รับคำถาม → retrieve context → generate answer ด้วย Claude
รัน: python query.py "อธิบาย RAG ให้หน่อย"
"""
import json
import sys
import os

import anthropic
import faiss
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

EMBED_MODEL = "all-MiniLM-L6-v2"
INDEX_PATH = "index.faiss"
META_PATH = "index_meta.json"
TOP_K = 4
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # เร็ว + ประหยัด สำหรับ demo


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    model = SentenceTransformer(EMBED_MODEL)
    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    vec = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, ids = index.search(vec, top_k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        results.append({**meta[idx], "score": float(score)})
    return results


def generate(query: str, context_chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[source: {c['source']}]\n{c['text']}" for c in context_chunks
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=(
            "You are a helpful assistant. Answer the user's question using ONLY "
            "the provided context. If the context doesn't contain the answer, "
            "say so clearly. Do not hallucinate."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            }
        ],
    )
    return response.content[0].text


def main(query: str) -> None:
    print(f"\n🔍 query: {query}\n")

    chunks = retrieve(query)
    print(f"retrieved {len(chunks)} chunks:")
    for i, c in enumerate(chunks, 1):
        print(f"  [{i}] score={c['score']:.3f} | {c['source']} | {c['text'][:80]}...")

    print("\n⚙️  generating answer...\n")
    answer = generate(query, chunks)
    print(f"📝 answer:\n{answer}\n")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is this document about?"
    main(q)
