"""
ingest.py — โหลด documents → chunk → embed → บันทึก FAISS index
รัน: python ingest.py --docs sample_docs/
"""
import argparse
import json
import os
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

CHUNK_SIZE = 512      # ตัวอักษร
CHUNK_OVERLAP = 64
EMBED_MODEL = "all-MiniLM-L6-v2"
INDEX_PATH = "index.faiss"
META_PATH = "index_meta.json"


def load_docs(docs_dir: str) -> list[dict]:
    docs = []
    for path in Path(docs_dir).rglob("*.txt"):
        text = path.read_text(encoding="utf-8")
        docs.append({"source": str(path), "text": text})
    return docs


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def build_index(docs: list[dict]) -> None:
    model = SentenceTransformer(EMBED_MODEL)
    all_chunks = []
    meta = []

    for doc in tqdm(docs, desc="chunking"):
        for chunk in chunk_text(doc["text"]):
            all_chunks.append(chunk)
            meta.append({"source": doc["source"], "text": chunk})

    print(f"embedding {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner Product = cosine (ถ้า normalize แล้ว)
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"✓ index saved — {index.ntotal} vectors, dim={dim}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="sample_docs/", help="โฟลเดอร์ที่เก็บ .txt files")
    args = parser.parse_args()

    docs = load_docs(args.docs)
    print(f"loaded {len(docs)} documents")
    build_index(docs)
