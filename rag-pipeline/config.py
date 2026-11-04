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
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# ---- chunking ----
CHUNK_SIZE = _env_int("RAG_CHUNK_SIZE", 512)          # ขนาด chunk เป้าหมาย (ตัวอักษร)
CHUNK_OVERLAP = _env_int("RAG_CHUNK_OVERLAP", 64)        # ส่วนซ้อนระหว่าง chunk กันบริบทขาด
RESPECT_HEADINGS = True   # ตัด chunk ตามหัวข้อ markdown (#, ##) ก่อนค่อยตัดตามขนาด

# ---- embedding / vector store ----
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")   # รองรับไทย
DATA_DIR = Path(os.getenv("RAG_DATA_DIR", Path(__file__).resolve().parent / "data"))
INDEX_PATH = str(DATA_DIR / "index.faiss")
META_PATH = str(DATA_DIR / "index_meta.json")
BM25_PATH = str(DATA_DIR / "index_bm25.json")   # เก็บ tokenized corpus สำหรับ sparse search

# ---- retrieval (hybrid) ----
TOP_K = _env_int("RAG_TOP_K", 4)                 # จำนวน chunk สุดท้ายที่ส่งให้ LLM
CANDIDATE_K = 20          # จำนวน candidate ก่อน rerank (ดึงเผื่อจากทั้ง dense + bm25)
RRF_K = 60                # ค่าคงที่ Reciprocal Rank Fusion (มาตรฐาน ~60)
USE_RERANK = _env_bool("RAG_USE_RERANK", False)   # เปิดเมื่อเลือก reranker ที่เหมาะกับภาษาเอกสาร
RERANK_MODEL = os.getenv("RAG_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# ---- generation ----
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")   # anthropic หรือ ollama
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = _env_int("OLLAMA_TIMEOUT", 300)
MAX_TOKENS = _env_int("RAG_MAX_TOKENS", 1024)
USE_PROMPT_CACHING = True   # cache system prompt ข้าม request (ลด cost/latency — node 09)

# ---- misc ----
def api_key() -> str:
    """ดึง ANTHROPIC_API_KEY จาก env — error ชัดถ้าไม่ตั้ง"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ตั้ง ANTHROPIC_API_KEY ก่อน (เช่นในไฟล์ .env)")
    return key
