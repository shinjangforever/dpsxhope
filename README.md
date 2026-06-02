# dpsxhope

> **EN:** Practical AI engineering — RAG pipelines, LLM APIs, agent workflows, local models, and REST APIs across Python and Node.js.
> **TH:** AI engineering จากของจริง — RAG pipeline, LLM API, agent workflow, local models และ REST API เขียนด้วย Python และ Node.js

โปรเจกต์นี้รวม implementation ของ pattern หลักทาง AI engineering ที่เน้นการใช้งานจริงใน production
Each module is self-contained, runnable, and built to demonstrate real understanding — not just framework usage.

**Languages / ภาษาโปรแกรม:** Python · JavaScript · TypeScript · Go · Rust · Bash/Shell · SQL · YAML  
**LLM Providers / ผู้ให้บริการ:** Anthropic Claude · Google Gemini · Ollama · llama.cpp · LM Studio · Jan · vLLM  
**Domains / โดเมน:** AI Engineering · Robotics (ROS 2) · Quantum Computing · Cloud & Infrastructure

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
| LLM API (Cloud) | `llm-eval/client.py` — Anthropic + Gemini unified client |
| LLM API (Local) | `local-models/` — Ollama, LM Studio, Jan, llama.cpp, vLLM |
| Prompt Design | structured output, few-shot, system prompts |
| Agent / Tool Use | `agent-demo/agent.py` — agentic loop + function calling จริง |
| Evaluation & Monitoring | relevance · faithfulness · recall@k · token logging |
| REST API (Node.js) | `ai-api/` — Express + streaming + rate limit |

---

### 4. `ai-api/` — REST API with Node.js (JavaScript)

**EN:** Express.js server exposing Claude as a REST API — single turn and streaming endpoints, with rate limiting.

**TH:** Express.js server ที่ห่อ Claude เป็น REST API — รองรับทั้งแบบ single turn และ streaming พร้อม rate limit

```
POST /api/chat         → single response (JSON)
POST /api/chat/stream  → streaming (Server-Sent Events)
GET  /health           → status check
```

```bash
cd ai-api
npm install
cp .env.example .env   # ใส่ ANTHROPIC_API_KEY

npm run dev            # รัน dev server พร้อม --watch

# ทดสอบ
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is RAG?"}'
```

---

### 5. `local-models/` — Local LLM Engines (Python)

**EN:** Run LLMs locally — zero API cost, works offline. Unified client supporting Ollama, LM Studio, Jan, llama.cpp, and vLLM.

**TH:** รัน LLM บนเครื่องตัวเอง — ไม่เสียค่า API, ทำงาน offline ได้ unified client รองรับ Ollama, LM Studio, Jan, llama.cpp และ vLLM

Supported engines / engine ที่รองรับ:

| Engine | Port | Interface |
|--------|------|-----------|
| Ollama | 11434 | Ollama API |
| LM Studio | 1234 | OpenAI-compatible |
| Jan | 1337 | OpenAI-compatible |
| llama.cpp server | 8080 | OpenAI-compatible |
| vLLM | 8000 | OpenAI-compatible |

```bash
cd local-models

# Ollama (ติดตั้งก่อน: ollama.com)
ollama pull llama3.2
python ollama_client.py "อธิบาย RAG ให้หน่อย"

# Unified client — เปลี่ยน provider ด้วย 1 บรรทัด
python unified_client.py "Explain embeddings"
```

ดูรายละเอียดโมเดลและ VRAM requirements → [ENGINES.md](local-models/ENGINES.md)

---

### 6. `languages/` — Multi-language AI Examples

**EN:** Same AI patterns implemented across multiple programming languages.  
**TH:** pattern เดียวกัน เขียนด้วยหลายภาษา — เปรียบเทียบ trade-off แต่ละภาษาได้ทันที

| File | Language | สิ่งที่แสดง |
|------|----------|-----------|
| `go/llm_client.go` | **Go** | LLM API client — fast, low memory, no runtime |
| `rust/tokenizer.rs` | **Rust** | Token counting + text chunking — performance critical |
| `typescript/client.ts` | **TypeScript** | Type-safe LLM client + structured output + streaming |
| `bash/model_manager.sh` | **Bash/Shell** | Model management + health check + benchmarking |
| `sql/ai_logs_schema.sql` | **SQL** | PostgreSQL schema — logging, eval, knowledge metadata |
| `yaml/ai_stack.docker-compose.yml` | **YAML** | Full AI dev stack: Ollama + Postgres + Redis + API |

---

### 7. `domains/` — Applied AI in Specialized Fields

**EN:** AI applied to robotics, quantum computing, and cloud infrastructure.  
**TH:** AI ประยุกต์ใช้ใน robotics, quantum computing และ cloud infrastructure

| Directory | สิ่งที่แสดง |
|-----------|-----------|
| `robotics/ros2_llm_bridge.py` | ROS 2 + LLM — แปลงภาษาธรรมชาติเป็น robot command |
| `quantum/qiskit_intro.py` | Qiskit — Bell State, Grover Search, VQE + LLM explanation |
| `cloud-infra/README.md` | Docker · K8s · Terraform · GitHub Actions · Prometheus |

---

## Author / ผู้สร้าง

**Daranpat Pattarakanpong (Shin)**
Strategic optimizer · AI engineer in practice · building things that work
