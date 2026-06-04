"""
ingest.py — โหลด documents → chunk → embed → บันทึก FAISS index + metadata + BM25 corpus

pipeline:
  1. load_docs : อ่านไฟล์ .txt และ .md ทุกไฟล์ในโฟลเดอร์ (recursive)
  2. chunk     : เรียก chunk_document (chunking.py) แบบ semantic/heading-aware
  3. embed     : SentenceTransformer → normalize → float32
  4. index     : FAISS IndexFlatIP (cosine เพราะ normalize แล้ว) → เขียน INDEX_PATH
  5. meta      : เขียน META_PATH (list chunk dict พร้อม id/heading)
  6. bm25      : เขียน BM25_PATH (tokenized corpus + ids) ให้ retrieve โหลดได้ตรงๆ

รัน: python ingest.py --docs sample_docs/
"""
import argparse
import json
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import EMBED_MODEL, INDEX_PATH, META_PATH, BM25_PATH
from chunking import chunk_document

# tokenizer สำหรับ BM25 — ต้อง "ตรงกับ retrieve.py" เป๊ะ (lower + split ตัวที่ไม่ใช่ a-z0-9)
# มิฉะนั้น query กับ corpus จะ tokenize ไม่เหมือนกัน BM25 จะ match ไม่ตรง
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """lower + split ตาม non-alphanumeric, กรอง token ว่างทิ้ง"""
    return [t for t in _TOKEN_RE.split(text.lower()) if t]


def load_docs(docs_dir: str) -> list[dict]:
    """อ่าน .txt และ .md ทุกไฟล์ใน docs_dir (recursive) คืน [{"source","text"}]"""
    docs = []
    base = Path(docs_dir)
    paths = sorted(base.rglob("*.txt")) + sorted(base.rglob("*.md"))  # deterministic
    for path in paths:
        text = path.read_text(encoding="utf-8")
        docs.append({"source": str(path), "text": text})
    return docs


def build_index(docs: list[dict]) -> None:
    """สร้าง FAISS index + metadata + BM25 corpus จาก list ของ docs"""
    # 1) chunk ทุก doc → รวมเป็น all_chunks พร้อมรันเลข id ตั้งแต่ 0
    all_chunks: list[dict] = []
    next_id = 0
    for doc in tqdm(docs, desc="chunking"):
        for chunk in chunk_document(doc["text"], doc["source"]):
            chunk["id"] = next_id   # id unique ทั้ง index
            next_id += 1
            all_chunks.append(chunk)

    if not all_chunks:
        print("⚠ ไม่พบ chunk ใดเลย — ตรวจสอบโฟลเดอร์ docs")
        return

    # 2) embed + normalize (เพื่อใช้ cosine ผ่าน inner product)
    model = SentenceTransformer(EMBED_MODEL)
    texts = [c["text"] for c in all_chunks]
    print(f"embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")

    # 3) FAISS IndexFlatIP (cosine) → เขียนไฟล์
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, INDEX_PATH)

    # 4) META = list ของ chunk dict ทั้งหมด (มี id/heading ครบ) เรียงตรงกับ position ใน faiss
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # 5) BM25 corpus: tokenize ล่วงหน้าทุก chunk เก็บคู่กับ id (retrieve โหลดมาใช้ได้เลย)
    bm25 = {
        "corpus_tokens": [_tokenize(c["text"]) for c in all_chunks],
        "ids": [c["id"] for c in all_chunks],
    }
    with open(BM25_PATH, "w", encoding="utf-8") as f:
        json.dump(bm25, f, ensure_ascii=False)

    print(f"✓ index saved — {index.ntotal} vectors, dim={dim}, chunks={len(all_chunks)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="สร้าง index จากเอกสารใน docs dir")
    parser.add_argument("--docs", default="sample_docs/", help="โฟลเดอร์ที่เก็บ .txt / .md")
    args = parser.parse_args()

    docs = load_docs(args.docs)
    print(f"loaded {len(docs)} documents")
    build_index(docs)
