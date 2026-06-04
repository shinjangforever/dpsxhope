# rag-pipeline

RAG (Retrieval-Augmented Generation) pipeline แบบ production-minded ของ **DpcAgenticTeam**
ครบตั้งแต่ ingest เอกสาร → hybrid retrieve → rerank → generate คำตอบที่อ้างอิงแหล่งที่มา → ประเมินคุณภาพ

ทุกค่ากลางอยู่ใน `config.py` (shared contract) — แก้ที่เดียวมีผลทั้งระบบ

---

## สถาปัตยกรรม

```
            ┌─────────────────────────────────────────────────────────────┐
            │                        config.py                            │
            │   (CLAUDE_MODEL, TOP_K, CHUNK_SIZE, USE_PROMPT_CACHING ...)  │
            └─────────────────────────────────────────────────────────────┘
                                       │  ทุก module อ่านค่ากลางจากที่นี่
                                       ▼
   docs/*.txt
      │
      ▼
 ┌──────────┐   chunk    ┌──────────────┐   embed +    ┌──────────────────────┐
 │  ingest  │──────────▶ │   chunking   │──────────▶  │  index (FAISS + BM25) │
 │ load_docs│ (semantic/ │ chunk_document│  index      │  index.faiss / meta   │
 └──────────┘  heading)  └──────────────┘             └──────────────────────┘
                                                                  │
                              query ──────────────────────────────┤
                                                                  ▼
                                                  ┌────────────────────────────┐
                                                  │          retrieve          │
                                                  │  dense (vector) + BM25      │
                                                  │  → RRF fuse → cross-encoder │
                                                  │     rerank → top_k chunks   │
                                                  └────────────────────────────┘
                                                                  │  list[retrieved dict]
                                                                  ▼
                                                  ┌────────────────────────────┐
                                                  │          generate           │
                                                  │  format_context([1][2]..)   │
                                                  │  → Claude (prompt caching)  │
                                                  │  → คำตอบ + citations [n]    │
                                                  └────────────────────────────┘
                                                                  │
                                                                  ▼
                                                  ┌────────────────────────────┐
                                                  │          evaluate           │
                                                  │  recall@k / context_precision│
                                                  │  / faithfulness (LLM judge) │
                                                  └────────────────────────────┘
```

**Contract กลาง** (ห้ามเปลี่ยน) — chunk ที่ retrieve คืน:

```python
retrieved = {"id": int, "source": str, "heading": str, "text": str, "score": float}
```

---

## ฟีเจอร์

- **Chunking แบบ semantic / heading-aware** — ตัด chunk ตามหัวข้อ markdown (`#`, `##`) ก่อน
  แล้วค่อยซอยตามขนาด (`CHUNK_SIZE`/`CHUNK_OVERLAP`) เพื่อไม่ให้บริบทขาดกลางหัวข้อ
- **Hybrid retrieval (dense + sparse)** — รวมผล vector search (embedding) กับ BM25 (keyword)
  ด้วย **Reciprocal Rank Fusion (RRF)** ได้ทั้งความหมายและการ match คำตรงตัว
- **Cross-encoder rerank** — จัดอันดับ candidate ใหม่ด้วย cross-encoder ก่อนส่ง top_k ให้ LLM
- **Citations [n]** — `generate` สั่ง Claude ให้ตอบจาก context เท่านั้น และอ้างอิงหมายเลข `[n]` ทุกข้อความ
- **Prompt caching** — cache system prompt แบบ ephemeral (`USE_PROMPT_CACHING`) เพื่อลด cost/latency
- **Evaluation 3 metric** — `recall@k`, `context_precision`, `faithfulness` (ใช้ Claude เป็น judge)

---

## ติดตั้ง

```bash
pip install -r requirements.txt
```

ตั้งค่า API key ผ่านไฟล์ `.env` ที่โฟลเดอร์นี้:

```
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

> `config.api_key()` จะอ่านจาก environment และ error ทันทีถ้าไม่ได้ตั้ง

---

## วิธีรัน (ผ่าน pipeline.py)

ทุกขั้นเรียกผ่าน CLI orchestrator เดียว:

```bash
# 1) ingest — โหลดเอกสาร + สร้าง index
python pipeline.py ingest --docs sample_docs/

# 2) query — ถาม 1 คำถาม (โชว์ chunks ที่ดึง + score แล้วตามด้วยคำตอบพร้อม citations)
python pipeline.py query "RAG คืออะไร?"

# 3) eval — ประเมินคุณภาพทั้งชุด
python pipeline.py eval
```

แต่ละ module ก็รันเดี่ยวได้ เช่น `python generate.py "..."` หรือ `python evaluate.py`

---

## ไฟล์ / โมดูล

| ไฟล์            | หน้าที่ |
|-----------------|---------|
| `config.py`     | ค่ากลางทั้งหมด + `api_key()` (shared contract — ห้ามแก้) |
| `ingest.py`     | `load_docs()` โหลดเอกสาร, `build_index()` chunk + embed + บันทึก index |
| `chunking.py`   | `chunk_document()` ตัด chunk แบบ semantic/heading-aware |
| `retrieve.py`   | `retrieve(query, top_k)` hybrid (dense+BM25) → RRF → rerank → top_k |
| `generate.py`   | `format_context()` สร้าง context มีหมายเลข, `generate()` เรียก Claude + caching + citations |
| `evaluate.py`   | `recall_at_k`, `context_precision`, `faithfulness_check`, `run_eval()` |
| `pipeline.py`   | CLI orchestrator: subcommands `ingest` / `query` / `eval` |
| `requirements.txt` | dependency ทั้งหมด |
| `sample_docs/`  | เอกสารตัวอย่างสำหรับ ingest |

---

## หมายเหตุ: graceful degradation

ระบบออกแบบให้ทำงานได้แม้ optional dependency บางตัวไม่มี:

- **ไม่มี `rank_bm25`** → ข้าม sparse search ใช้ dense (vector) อย่างเดียว
- **ไม่มี `CrossEncoder` (sentence-transformers reranker)** → ข้าม rerank ใช้ลำดับจาก RRF แทน
- **faithfulness parse JSON ไม่ได้ / API error** → คืน `{"faithful": None, ...}` แทนที่จะ crash

หมายความว่าฟีเจอร์ขั้นสูง (hybrid / rerank) เป็น "เสริม" — ถ้าสภาพแวดล้อมไม่พร้อม
pipeline ยังเดินต่อได้ด้วยคุณภาพที่ลดหลั่นลงมาอย่างปลอดภัย ไม่พังทั้งระบบ
