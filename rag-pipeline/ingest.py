"""
ingest.py — โหลด documents → chunk → embed → บันทึก FAISS index + metadata + BM25 corpus

pipeline:
  1. load_docs : อ่านไฟล์ .txt, .md และ .pdf ทุกไฟล์ในโฟลเดอร์ (recursive)
  2. chunk     : เรียก chunk_document (chunking.py) แบบ semantic/heading-aware
  3. embed     : SentenceTransformer → normalize → float32
  4. index     : FAISS IndexFlatIP (cosine เพราะ normalize แล้ว) → เขียน INDEX_PATH
  5. meta      : เขียน META_PATH (list chunk dict พร้อม id/heading)
  6. bm25      : เขียน BM25_PATH (tokenized corpus + ids) ให้ retrieve โหลดได้ตรงๆ

รัน: python ingest.py --docs /path/to/your-docs
"""
import argparse
import json
import os
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import BM25_PATH, DATA_DIR, EMBED_MODEL, INDEX_PATH, META_PATH
from chunking import chunk_document
from textutil import clean_extracted_text, tokenize

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}

def read_document(path: Path) -> str:
    """อ่านข้อความจากไฟล์ที่รองรับ"""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        raw = "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        lost = raw.count("\x00")
        if lost:
            print(f"⚠ {path.name}: PDF สูญเสียเครื่องหมายบางตัว {lost} ตำแหน่ง (มักเป็นวรรณยุกต์/การันต์ของภาษาไทย) "
                  "การค้นด้วยคำยังใช้ได้ แต่ข้อความที่แสดงอาจขาดเครื่องหมาย ถ้าเป็นไปได้ให้ใช้ไฟล์ต้นฉบับ .md/.txt")
        return clean_extracted_text(raw)
    return path.read_text(encoding="utf-8")


def load_docs(docs_dir: str) -> list[dict]:
    """อ่านไฟล์ที่รองรับใน docs_dir (recursive) คืน [{"source","text"}] และข้ามไฟล์ที่อ่านไม่ได้"""
    base = Path(docs_dir)
    if not base.is_dir():
        raise SystemExit(f"ไม่พบโฟลเดอร์เอกสาร: {base}")

    docs, skipped = [], []
    paths = sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    for path in paths:
        try:
            text = read_document(path)
        except Exception as exc:
            skipped.append(f"{path}: {exc}")
            continue
        if text.strip():
            docs.append({"source": str(path), "text": text})
        else:
            skipped.append(f"{path}: ไม่พบข้อความ")

    for item in skipped:
        print(f"⚠ ข้าม {item}")
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_index = f"{INDEX_PATH}.tmp"
    temp_meta = f"{META_PATH}.tmp"
    temp_bm25 = f"{BM25_PATH}.tmp"
    faiss.write_index(index, temp_index)

    # 4) META = list ของ chunk dict ทั้งหมด (มี id/heading ครบ) เรียงตรงกับ position ใน faiss
    with open(temp_meta, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # 5) BM25 corpus: tokenize ล่วงหน้าทุก chunk เก็บคู่กับ id (retrieve โหลดมาใช้ได้เลย)
    bm25 = {
        "corpus_tokens": [tokenize(c["text"]) for c in all_chunks],
        "ids": [c["id"] for c in all_chunks],
    }
    with open(temp_bm25, "w", encoding="utf-8") as f:
        json.dump(bm25, f, ensure_ascii=False)

    # เปลี่ยนไฟล์หลังเขียนครบ เพื่อไม่ให้ index เดิมเสียเมื่อ ingest ล้มเหลวกลางทาง
    for temp, final in ((temp_index, INDEX_PATH), (temp_meta, META_PATH), (temp_bm25, BM25_PATH)):
        os.replace(temp, final)

    print(f"✓ index saved — {index.ntotal} vectors, dim={dim}, chunks={len(all_chunks)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="สร้าง index จากเอกสารใน docs dir")
    parser.add_argument("--docs", default="sample_docs/", help="โฟลเดอร์ที่เก็บ .txt, .md หรือ .pdf")
    args = parser.parse_args()

    docs = load_docs(args.docs)
    print(f"loaded {len(docs)} documents")
    build_index(docs)
