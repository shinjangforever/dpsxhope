"""
config.py — ค่ากลางของ RAG pipeline ทั้งหมด (shared contract)
แก้ที่นี่ที่เดียว ทุก module อ่านจากที่นี่

ทุก module ใช้ "contract" ของ chunk dict ตามนี้:
    chunk = {
        "id": int,            # ลำดับ chunk (unique ทั้ง index)
        "source": str,        # path ไฟล์ต้นทาง
        "heading": str,       # หัวข้อ/section ที่ chunk นี้อยู่ ("" ถ้าไม่มี)
        "text": str,          # เนื้อ chunk
    }
retrieved dict = chunk dict + {"score": float}  (คะแนนความเกี่ยวข้องหลัง fuse/rerank)
"""
import os

# ---- chunking ----
CHUNK_SIZE = 512          # ขนาด chunk เป้าหมาย (ตัวอักษร)
CHUNK_OVERLAP = 64        # ส่วนซ้อนระหว่าง chunk กันบริบทขาด
RESPECT_HEADINGS = True   # ตัด chunk ตามหัวข้อ markdown (#, ##) ก่อนค่อยตัดตามขนาด

# ---- embedding / vector store ----
EMBED_MODEL = "all-MiniLM-L6-v2"
INDEX_PATH = "index.faiss"
META_PATH = "index_meta.json"
BM25_PATH = "index_bm25.json"   # เก็บ tokenized corpus สำหรับ sparse search

# ---- retrieval (hybrid) ----
TOP_K = 4                 # จำนวน chunk สุดท้ายที่ส่งให้ LLM
CANDIDATE_K = 20          # จำนวน candidate ก่อน rerank (ดึงเผื่อจากทั้ง dense + bm25)
RRF_K = 60                # ค่าคงที่ Reciprocal Rank Fusion (มาตรฐาน ~60)
USE_RERANK = True         # เปิด cross-encoder rerank (ถ้า lib มี ไม่งั้น degrade เป็น RRF)
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ---- generation ----
CLAUDE_MODEL = "claude-haiku-4-5-20251001"   # เร็ว + ประหยัด สำหรับ pipeline
MAX_TOKENS = 1024
USE_PROMPT_CACHING = True   # cache system prompt ข้าม request (ลด cost/latency — node 09)

# ---- misc ----
def api_key() -> str:
    """ดึง ANTHROPIC_API_KEY จาก env — error ชัดถ้าไม่ตั้ง"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ตั้ง ANTHROPIC_API_KEY ก่อน (เช่นในไฟล์ .env)")
    return key
