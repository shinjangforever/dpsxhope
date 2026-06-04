"""
retrieve.py — hybrid retrieval ของ RAG pipeline
    dense (FAISS) + sparse (BM25) → RRF fusion → optional cross-encoder rerank

public API: retrieve(query, top_k) -> list[retrieved dict]
    retrieved dict = chunk dict + {"score": float}  (เรียงจาก score มาก→น้อย)

ทุกจุดที่พึ่ง lib ภายนอกจะ degrade อย่างนุ่มนวล (ไม่พังทั้ง pipeline)
รัน: python retrieve.py "คำถามของฉัน"
"""
import json
import re
import sys

import config

# ---- import แบบ optional + degrade ----
# faiss + sentence-transformers จำเป็นต่อ dense search (ถ้าไม่มีถือว่า dense ใช้ไม่ได้)
try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _DENSE_OK = True
except Exception:  # pragma: no cover - degrade ถ้า lib หาย
    _DENSE_OK = False

# rank_bm25 ใช้สำหรับ sparse search — ถ้าไม่มีให้ sparse คืน [] (dense ล้วน)
try:
    from rank_bm25 import BM25Okapi
    _BM25_LIB_OK = True
except Exception:  # pragma: no cover
    _BM25_LIB_OK = False

# CrossEncoder ใช้ตอน rerank — ถ้าไม่มีให้ degrade เป็นการเรียงตาม rrf_score
try:
    from sentence_transformers import CrossEncoder
    _RERANK_LIB_OK = True
except Exception:  # pragma: no cover
    _RERANK_LIB_OK = False


# ---- tokenizer ----
# ต้องเหมือน ingest ฝั่ง BM25: lower + ตัดด้วย regex ที่ไม่ใช่ alphanumeric
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """แปลง text → list ของ token (lower + split ตัวที่ไม่ใช่ a-z0-9) ตัด token ว่างทิ้ง"""
    return [t for t in _TOKEN_RE.split(text.lower()) if t]


# ---- resource cache (module-level, lazy) ----
# โหลด model/index/meta/bm25 ครั้งเดียวแล้ว cache ไว้ กันโหลดซ้ำตอน eval วนหลายรอบ
_embed_model = None       # SentenceTransformer (dense)
_index = None             # faiss index
_meta = None              # list[chunk dict] เรียงตาม position ใน faiss
_id_to_chunk = None       # dict: id -> chunk dict (lookup เร็ว)
_bm25 = None              # BM25Okapi object
_bm25_ids = None          # list[id] เรียงตรงกับ corpus ที่ใส่ BM25
_reranker = None          # CrossEncoder
_reranker_loaded = False  # flag กันพยายามโหลด reranker ซ้ำเมื่อโหลดล้มเหลว


def _get_embed_model():
    """โหลด embedding model (lazy + cache) — คืน None ถ้า lib/โหลดไม่ได้"""
    global _embed_model
    if not _DENSE_OK:
        return None
    if _embed_model is None:
        _embed_model = SentenceTransformer(config.EMBED_MODEL)
    return _embed_model


def _get_index():
    """โหลด faiss index (lazy + cache) — คืน None ถ้าโหลดไม่ได้"""
    global _index
    if not _DENSE_OK:
        return None
    if _index is None:
        try:
            _index = faiss.read_index(config.INDEX_PATH)
        except Exception:
            return None
    return _index


def _get_meta():
    """โหลด meta (list[chunk dict]) + สร้าง id->chunk map (lazy + cache)"""
    global _meta, _id_to_chunk
    if _meta is None:
        with open(config.META_PATH, encoding="utf-8") as f:
            _meta = json.load(f)
        # สร้าง lookup จาก id ไปยัง chunk dict เต็ม
        _id_to_chunk = {c["id"]: c for c in _meta}
    return _meta


def _get_id_to_chunk() -> dict:
    """คืน map id -> chunk dict (โหลด meta ก่อนถ้ายังไม่โหลด)"""
    if _id_to_chunk is None:
        _get_meta()
    return _id_to_chunk


def _get_bm25():
    """โหลด BM25 จาก corpus_tokens (lazy + cache) — คืน (None, None) ถ้า lib ไม่มี/โหลดไม่ได้"""
    global _bm25, _bm25_ids
    if not _BM25_LIB_OK:
        return None, None
    if _bm25 is None:
        try:
            with open(config.BM25_PATH, encoding="utf-8") as f:
                data = json.load(f)
            corpus_tokens = data["corpus_tokens"]
            _bm25_ids = data["ids"]
            _bm25 = BM25Okapi(corpus_tokens)
        except Exception:
            return None, None
    return _bm25, _bm25_ids


def _get_reranker():
    """โหลด CrossEncoder (lazy + cache) — คืน None ถ้าปิด/lib ไม่มี/โหลดไม่ได้"""
    global _reranker, _reranker_loaded
    if not config.USE_RERANK or not _RERANK_LIB_OK:
        return None
    if not _reranker_loaded:
        _reranker_loaded = True  # ตั้ง flag ก่อน กันพยายามโหลดซ้ำถ้าล้มเหลว
        try:
            _reranker = CrossEncoder(config.RERANK_MODEL)
        except Exception:
            _reranker = None
    return _reranker


# ---- dense search ----
def dense_search(query: str, k: int) -> list:
    """
    encode query (normalize) → faiss search → คืน list ของ (id, rank)
    rank เริ่มที่ 0 (อันดับดีสุดก่อน) — degrade เป็น [] ถ้า dense ใช้ไม่ได้
    """
    model = _get_embed_model()
    index = _get_index()
    if model is None or index is None:
        return []

    meta = _get_meta()
    vec = model.encode([query], normalize_embeddings=True)
    vec = np.asarray(vec, dtype="float32")
    _, idxs = index.search(vec, k)

    results = []
    for rank, pos in enumerate(idxs[0]):
        if pos == -1:
            continue
        # pos = ตำแหน่งใน faiss = index ใน meta → ดึง id จริงของ chunk
        results.append((meta[int(pos)]["id"], rank))
    return results


# ---- sparse search (BM25) ----
def sparse_search(query: str, k: int) -> list:
    """
    BM25 บน corpus_tokens → score → top k → คืน list ของ (id, rank)
    degrade เป็น [] ถ้า rank_bm25 import ไม่ได้ (ให้ hybrid ใช้ dense ล้วน)
    """
    bm25, bm25_ids = _get_bm25()
    if bm25 is None or bm25_ids is None:
        return []

    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # จัดอันดับ index ตาม score มาก→น้อย แล้วตัด top k
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [(bm25_ids[i], rank) for rank, i in enumerate(ranked)]


# ---- RRF fusion ----
def reciprocal_rank_fusion(dense_ranks: list, sparse_ranks: list, k: int = config.RRF_K) -> list:
    """
    Reciprocal Rank Fusion: รวมอันดับจากหลาย list
    score(id) = Σ 1/(k + rank) ของทุก list ที่ id นั้นปรากฏ
    คืน list ของ (id, rrf_score) เรียงจากมาก→น้อย
    """
    scores: dict = {}
    for ranks in (dense_ranks, sparse_ranks):
        for doc_id, rank in ranks:
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


# ---- rerank ----
def rerank(query: str, candidates: list) -> list:
    """
    rerank candidates ด้วย cross-encoder ถ้าทำได้
        candidates = list ของ (id, rrf_score)
    คืน list[retrieved dict] (chunk เต็ม + score) เรียงจากมาก→น้อย

    ถ้า reranker ใช้ไม่ได้ → degrade: ใช้ rrf_score เป็น score, เรียงตามลำดับ candidate เดิม
    """
    id_to_chunk = _get_id_to_chunk()
    reranker = _get_reranker()

    if reranker is None:
        # degrade: คง rrf_score เดิมเป็น score (candidates เรียงมาแล้ว)
        out = []
        for doc_id, rrf_score in candidates:
            chunk = id_to_chunk.get(doc_id)
            if chunk is None:
                continue
            out.append({**chunk, "score": float(rrf_score)})
        return out

    # ใช้ cross-encoder ให้คะแนนคู่ (query, chunk_text)
    chunks = []
    pairs = []
    for doc_id, _ in candidates:
        chunk = id_to_chunk.get(doc_id)
        if chunk is None:
            continue
        chunks.append(chunk)
        pairs.append((query, chunk["text"]))

    if not pairs:
        return []

    try:
        ce_scores = reranker.predict(pairs)
    except Exception:
        # ถ้า predict พัง → degrade เป็นเรียงตาม candidate เดิม + rrf_score
        rrf_map = dict(candidates)
        return [{**c, "score": float(rrf_map.get(c["id"], 0.0))} for c in chunks]

    scored = [{**c, "score": float(s)} for c, s in zip(chunks, ce_scores)]
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored


# ---- public API ----
def retrieve(query: str, top_k: int = config.TOP_K) -> list:
    """
    pipeline เต็ม:
        dense_search + sparse_search (k=CANDIDATE_K)
        → RRF fusion
        → เอา CANDIDATE_K ตัวแรก
        → rerank
        → คืน top_k retrieved dict (chunk เต็ม + score) เรียงมาก→น้อย

    นี่คือ public API ที่ generate.py / evaluate.py เรียก (ชื่อ retrieve เป๊ะ)
    """
    dense_ranks = dense_search(query, config.CANDIDATE_K)
    sparse_ranks = sparse_search(query, config.CANDIDATE_K)

    fused = reciprocal_rank_fusion(dense_ranks, sparse_ranks, k=config.RRF_K)
    candidates = fused[: config.CANDIDATE_K]

    reranked = rerank(query, candidates)
    return reranked[:top_k]


# ---- CLI ----
if __name__ == "__main__":
    # รับ query จาก argv (ต่อทุก arg เป็นประโยคเดียว) — มี default ถ้าไม่ใส่
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is this document about?"
    print(f"\nquery: {q}\n")

    results = retrieve(q)
    print(f"retrieved {len(results)} chunks:")
    for c in results:
        text_preview = c["text"][:80].replace("\n", " ")
        print(
            f"  id={c['id']} score={c['score']:.4f} | "
            f"{c.get('source', '')} | {c.get('heading', '')} | {text_preview}"
        )
