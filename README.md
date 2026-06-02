# dpsxhope

> **EN:** Practical AI engineering — RAG pipelines, LLM APIs, and agent workflows built from scratch.
> **TH:** AI engineering จากของจริง — RAG pipeline, LLM API และ agent workflow ที่เขียนขึ้นเองทุกส่วน

โปรเจกต์นี้รวม implementation ของ pattern หลักทาง AI engineering ที่เน้นการใช้งานจริงใน production
Each module is self-contained, runnable, and built to demonstrate real understanding — not just framework usage.

---

## Modules / โมดูล

### 1. `rag-pipeline/` — Retrieval-Augmented Generation

**EN:** A complete RAG system: ingest documents → embed → index → retrieve → generate → evaluate.

**TH:** ระบบ RAG ครบวงจร: นำเข้าเอกสาร → แปลงเป็น vector → สร้าง index → ค้นหา → สร้างคำตอบ → ประเมินผล

```
Documents (.txt)
    ↓ chunk + embed (sentence-transformers)
FAISS Index
    ↓ similarity search
Retrieved Context
    ↓ + user query
Claude API → Answer
    ↓
Evaluation (recall@k, faithfulness)
```

**Stack:** Python · FAISS · sentence-transformers · Anthropic Claude API

```bash
cd rag-pipeline
pip install -r requirements.txt
cp .env.example .env   # ใส่ ANTHROPIC_API_KEY

python ingest.py --docs sample_docs/
python query.py "What is RAG?"
python evaluate.py
```

---

### 2. `llm-eval/` — LLM API Client + Output Evaluation

**EN:** A unified client for Anthropic Claude and Google Gemini, plus an evaluator that scores LLM output on relevance, faithfulness, and format compliance.

**TH:** Client รวมสำหรับทั้ง Anthropic Claude และ Google Gemini พร้อม evaluator ที่วัดคุณภาพ output ใน 3 มิติ: ความเกี่ยวข้อง, ความน่าเชื่อถือ (hallucination check) และความถูกต้องของ format

Features / ฟีเจอร์:
- Provider-agnostic interface — สลับระหว่าง Claude และ Gemini โดยไม่ต้องแก้ logic หลัก
- Structured output extraction — ดึงข้อมูลแบบ JSON schema
- Faithfulness scoring via LLM-as-judge — ใช้ LLM ตรวจ LLM
- Request logging with token usage — บันทึก log พร้อมการใช้ token

```bash
cd llm-eval
pip install -r requirements.txt

python examples/structured_output.py
```

---

### 3. `agent-demo/` — Claude Agentic Loop (Tool Use)

**EN:** A working implementation of Claude's tool use API — the agent decides when to call tools and loops until it reaches a final answer.

**TH:** การใช้งาน tool use API ของ Claude จริงๆ — agent ตัดสินใจเองว่าจะเรียก tool ไหน แล้ว loop จนกว่าจะได้คำตอบสุดท้าย

Built-in tools / เครื่องมือในตัว:
- `calculate` — ประเมินนิพจน์คณิตศาสตร์อย่างปลอดภัย (ไม่มี hallucinated numbers)
- `text_search` — ค้นหา keyword ใน local files

```bash
cd agent-demo
pip install -r requirements.txt

python agent.py "What is sqrt(65536) and how many bits is that?"
```

---

## Setup / การติดตั้ง

**EN:** Each module has its own `requirements.txt`. Create a `.env` file in the module directory:

**TH:** แต่ละโมดูลมี `requirements.txt` ของตัวเอง สร้างไฟล์ `.env` ในโฟลเดอร์นั้น:

```env
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...          # สำหรับ llm-eval Gemini examples เท่านั้น
```

Python 3.11+ recommended / แนะนำ Python 3.11 ขึ้นไป

---

## Design Principles / หลักการออกแบบ

| EN | TH |
|----|-----|
| No magic — each file does one thing | ไม่ซ่อน logic — แต่ละไฟล์ทำสิ่งเดียว อ่านเข้าใจได้ทั้งหมด |
| Production-minded — logging, eval built in | คิดแบบ production — มี logging และ evaluation ตั้งแต่ต้น |
| Provider flexibility — not locked to one vendor | ไม่ผูกกับ vendor เดียว — เปลี่ยน LLM provider ได้ง่าย |
| Minimal dependencies — only what's needed | dependency น้อย — ใช้เฉพาะที่จำเป็นจริงๆ |

---

## Skills Demonstrated / ทักษะที่แสดง

| Area / ด้าน | Implementation |
|-------------|---------------|
| RAG Pipeline | `rag-pipeline/` — ingest → retrieve → generate ครบวงจร |
| LLM API | `llm-eval/client.py` — Anthropic + Gemini unified client |
| Prompt Design | structured output, few-shot, system prompts |
| Agent / Tool Use | `agent-demo/agent.py` — agentic loop + function calling จริง |
| Evaluation & Monitoring | relevance · faithfulness · recall@k · token logging |

---

## Author / ผู้สร้าง

**Daranpat Pattarakanpong (Shin)**
Strategic optimizer · AI engineer in practice · building things that work
