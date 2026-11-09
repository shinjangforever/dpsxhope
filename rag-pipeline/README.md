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

ตั้งค่าผ่านไฟล์ `.env` ที่ root ของ repo:

```bash
cp ../.env.example ../.env
```

ใช้ Claude ให้ใส่ `ANTHROPIC_API_KEY` ส่วนการรันในเครื่องโดยไม่ใช้ key ให้ตั้ง `LLM_PROVIDER=ollama` และ `OLLAMA_MODEL`

---

## นำไปใช้กับเอกสารของคุณ

```bash
python pipeline.py ingest --docs /path/to/your-docs
python pipeline.py query "นโยบายลาพักร้อนคืออะไร" --json
python pipeline.py eval --cases eval_cases.json --min-recall 0.8
```

รองรับ `.txt`, `.md` และ `.pdf` ที่มีข้อความ ค่าเริ่มต้นใช้ embedding หลายภาษาและ BM25 ที่รองรับข้อความไทย ส่วน PDF ที่เป็นภาพสแกนต้องทำ OCR ก่อน

เรียกจากแอป Python:

```python
from pipeline import ask

result = ask("นโยบายลาพักร้อนคืออะไร")
print(result["answer"], result["sources"])
```

| ต้องการเปลี่ยน | ตั้งค่า |
|---|---|
| ที่เก็บ index | `RAG_DATA_DIR` |
| โมเดล embedding | `RAG_EMBED_MODEL` |
| จำนวนแหล่งอ้างอิง | `RAG_TOP_K` |
| reranker | `RAG_USE_RERANK`, `RAG_RERANK_MODEL` |
| ผู้ให้บริการ LLM | `LLM_PROVIDER` หรือแก้ `complete()` ใน `generate.py` |

**ข้อจำกัด:** `ingest` สร้าง index ใหม่ทั้งหมด และยังไม่มีการแยกสิทธิ์รายเอกสาร ให้เพิ่มก่อนใช้กับข้อมูลที่แต่ละคนเข้าถึงไม่เท่ากัน ถ้าเปิด reranker ค่าเริ่มต้นเหมาะกับภาษาอังกฤษ ควรเลือกโมเดลที่รองรับภาษาไทยเมื่อใช้เอกสารไทย

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

คำสั่งเพิ่มเติม:

- `python pipeline.py chat` ถามต่อเนื่องหลายข้อ โหลดโมเดลครั้งเดียว (เว้นว่างหรือพิมพ์ exit เพื่อออก)
- `python pipeline.py chat --search-only` แสดงเฉพาะช่วงเอกสารที่ค้นเจอ ไม่เรียก AI จึงไม่ต้องมี key หรือ Ollama
- `ingest` ข้ามไฟล์ที่ชื่อขึ้นต้นด้วย `_` หรือ `.` และแจ้งจำนวนที่ข้าม เปลี่ยนชื่อไฟล์ถ้าต้องการให้ถูกอ่าน
- ถ้าไม่ถนัด terminal ใช้ `python hope.py` ที่ root ของ repo แทนได้ (เมนูภาษาไทย)

---

## ภาษาไทยและ PDF

ชุดทดสอบไทยอยู่ที่ `sample_docs_th/` (8 ไฟล์) กับ `eval_cases_th.json` (30 ข้อ แต่ละข้อระบุ `expected_source`)

```bash
python pipeline.py ingest --docs sample_docs_th/
python pipeline.py eval --cases eval_cases_th.json --no-judge
```

ผลที่วัดเมื่อ 2026-11-08 ด้วย `paraphrase-multilingual-MiniLM-L12-v2` (เปรียบเทียบคร่าวๆ ได้ ไม่ใช่ benchmark เพราะเอกสารและคำถามเขียนโดยผู้ดูแล repo เอง):

| ข้อมูล | chunk | ไฟล์ถูกอันดับ 1 | ไฟล์ถูกอยู่ใน top-4 |
|---|---|---|---|
| `.md` ไทย (hybrid) | 31 | 28/30 | 30/30 |
| PDF ไทยที่ Edge สร้าง (hybrid) | 9 | 26/30 | 29/30 |

สองแถวนี้เทียบกันตรงๆ ไม่ได้ เพราะ PDF ไม่มีหัวข้อ markdown จึงเหลือประมาณหนึ่ง chunk ต่อเอกสาร

ข้อควรระวังกับ PDF ภาษาไทย:

- PDF ที่สร้างจากเบราว์เซอร์อาจทำให้ไม้เอกที่ซ้อนบนสระและการันต์หายไป ตอนนี้ `ingest` ซ่อมอักขระเสีย ตัดวรรณยุกต์และการันต์ออกตอนแยกคำ และเตือนเมื่อพบการสูญเสีย แต่ข้อความที่แสดงเป็น citation จะยังขาดเครื่องหมายเหล่านั้น
- ตรวจกับ PDF จาก Edge เพียงตัวอย่างเดียว PDF จาก Word, LibreOffice หรือระบบอื่นอาจต่างออกไป
- PDF แบบสแกนต้องใช้ OCR ซึ่งยังไม่รองรับ
- ถ้ามีไฟล์ต้นฉบับ `.md` หรือ `.txt` ให้ใช้ไฟล์นั้นแทน
- หลังอัปเกรดที่เปลี่ยนตัวแยกคำ ต้องรัน `ingest` ใหม่ ไม่เช่นนั้นคำที่มีวรรณยุกต์จะค้นไม่เจอ

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
| `textutil.py`   | `tokenize()` แยกคำไทย/ละติน, `clean_extracted_text()` ซ่อมข้อความจาก PDF, `fold()` เทียบข้อความโดยไม่สนวรรณยุกต์ |
| `sample_docs/`  | เอกสารตัวอย่างสำหรับ ingest |
| `sample_docs_th/`, `eval_cases_th.json` | คลังเอกสารไทยและชุดคำถาม 30 ข้อสำหรับวัดการค้นหา |

---

## หมายเหตุ: graceful degradation

ระบบออกแบบให้ทำงานได้แม้ optional dependency บางตัวไม่มี:

- **ไม่มี `rank_bm25`** → ข้าม sparse search ใช้ dense (vector) อย่างเดียว
- **ไม่มี `CrossEncoder` (sentence-transformers reranker)** → ข้าม rerank ใช้ลำดับจาก RRF แทน
- **faithfulness parse JSON ไม่ได้ / API error** → คืน `{"faithful": None, ...}` แทนที่จะ crash

หมายความว่าฟีเจอร์ขั้นสูง (hybrid / rerank) เป็น "เสริม" — ถ้าสภาพแวดล้อมไม่พร้อม
pipeline ยังเดินต่อได้ด้วยคุณภาพที่ลดหลั่นลงมาอย่างปลอดภัย ไม่พังทั้งระบบ
