# dpsxhope

> **EN:** Practical AI engineering — RAG pipelines, LLM APIs, agent workflows, engine control, and multi-language implementations.  
> **TH:** AI engineering จากของจริง — RAG, LLM API, agent workflow, ควบคุม engine และ implementation หลายภาษา

โปรเจกต์นี้รวม implementation ของ pattern หลักทาง AI engineering ที่เน้นการใช้งานจริง
Each module is self-contained, runnable, and built to demonstrate real understanding.

**Languages / ภาษา:** Python · JavaScript · TypeScript · Go · Rust · Bash · SQL · YAML  
**Engines / เครื่องยนต์:** Anthropic Claude · Gemini · Ollama · llama.cpp · LM Studio · Jan · vLLM  
**Domains / โดเมน:** AI Engineering · Robotics (ROS 2) · Quantum · Cloud & Infrastructure

---

## System Overview / ภาพรวมระบบ

```
┌─────────────────────────────────────────────────────────────┐
│                        dpsxhope                             │
│                                                             │
│  Input ──► Agent Workflows ──► Engine Controller            │
│                │                      │                     │
│           ┌────▼────┐         ┌───────▼────────┐           │
│           │  Steps  │         │  Chat Format   │           │
│           │classify │         │llama3/chatml/  │           │
│           │research │         │gemma/deepseek  │           │
│           │summarize│         └───────┬────────┘           │
│           │evaluate │                 │                     │
│           └────┬────┘         ┌───────▼────────┐           │
│                │               │  LLM Engines   │           │
│           ┌────▼────┐         │ ollama  :11434 │           │
│           │  Tools  │         │ llamacpp:8080  │           │
│           │calculate│         │ lmstudio:1234  │           │
│           │t_search │         │ cloud API      │           │
│           └─────────┘         └───────┬────────┘           │
│                                       │                     │
│  RAG Pipeline ◄── FAISS Index ◄── Embeddings               │
│  SQL Logs  ◄── Evaluator ◄── Response                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start / เริ่มใช้งาน

```bash
# 1. Clone
git clone https://github.com/shinjangforever/dpsxhope.git
cd dpsxhope

# 2. ตรวจสอบ engines ที่รันอยู่
python local-models/engine/controller.py status

# 3. เปิด Ollama + ดาวน์โหลดโมเดล
python local-models/engine/controller.py start ollama
python local-models/engine/controller.py pull llama3.2

# 4. รัน RAG pipeline
cd rag-pipeline && pip install -r requirements.txt
python ingest.py --docs sample_docs/
python query.py "What is RAG?"

# 5. รัน agent workflow
cd agent-demo
python workflows/workflow_runner.py workflows/examples/research_workflow.json "Explain RAG"
```

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

#### llama.cpp — คำสั่งครบชุด / Full Command Reference

```bash
# ── ติดตั้ง / Install ────────────────────────────────────────
git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp

# CPU only
cmake -B build && cmake --build build -j$(nproc)

# + AVX2 (Intel/AMD modern CPU — เร็วขึ้น ~30%)
cmake -B build -DGGML_AVX2=ON && cmake --build build -j$(nproc)

# + CUDA (NVIDIA GPU)
cmake -B build -DGGML_CUDA=ON && cmake --build build -j$(nproc)

# + Metal (Apple Silicon)
cmake -B build -DGGML_METAL=ON && cmake --build build -j$(nproc)

# + ROCm (AMD GPU)
cmake -B build -DGGML_HIPBLAS=ON && cmake --build build -j$(nproc)

# ARM / Raspberry Pi / Termux
cmake -B build -DGGML_NEON=ON && cmake --build build -j4

# ── Server (OpenAI-compatible API) ──────────────────────────
./build/bin/llama-server -m model.gguf --port 8080

# ปรับ thread + context size
./build/bin/llama-server -m model.gguf -t 8 --ctx-size 8192 --port 8080

# GPU layers (offload ไป GPU บางส่วน — ประหยัด RAM)
./build/bin/llama-server -m model.gguf --n-gpu-layers 20 --port 8080

# ── Chat CLI ────────────────────────────────────────────────
./build/bin/llama-cli -m model.gguf --interactive -p "You are a helpful assistant."

# one-shot
./build/bin/llama-cli -m model.gguf -p "สวัสดี" -n 200 --no-display-prompt

# ── Perplexity / Benchmark ──────────────────────────────────
./build/bin/llama-perplexity -m model.gguf -f test.txt

# throughput test
./build/bin/llama-bench -m model.gguf -n 512 -ngl 0

# ── Convert & Quantize ──────────────────────────────────────
# HuggingFace → GGUF
python convert_hf_to_gguf.py /path/to/model --outfile model.gguf

# quantize (Q4_K_M แนะนำ)
./build/bin/llama-quantize model-f16.gguf model-q4_k_m.gguf Q4_K_M

# ── Embeddings server ───────────────────────────────────────
./build/bin/llama-server -m embed-model.gguf --embeddings --port 8080

# ── Script อัตโนมัติ (auto-detect arch) ─────────────────────
bash local-models/llamacpp/server.sh /path/to/model.gguf 8080
```

---

### 5.5 `local-models/engine/` — Engine Control + Chat Format

**EN:** Programmatic control of all LLM engines + correct prompt formatting per model family.  
**TH:** ควบคุม engine ทุกตัวด้วย code + จัด prompt format ให้ถูกต้องตามแต่ละโมเดล

```bash
# ── Engine Controller ────────────────────────────────────────
python local-models/engine/controller.py status          # ตรวจทุก engine
python local-models/engine/controller.py start ollama    # เปิด Ollama
python local-models/engine/controller.py pull qwen2.5:7b # ดาวน์โหลดโมเดล
python local-models/engine/controller.py switch llama3.2 qwen2.5:7b  # สลับโมเดล
python local-models/engine/controller.py bench qwen2.5:7b            # benchmark
python local-models/engine/controller.py stop ollama     # ปิด Ollama

# ── Chat Format (prompt template ต่างกันต่างโมเดล) ───────────
python local-models/engine/chat_format.py
```

**Chat Format families / รูปแบบ prompt ตามโมเดล:**

| Format | โมเดล | Template style |
|--------|--------|---------------|
| **Llama 3** | llama3.x | `<\|start_header_id\|>role<\|end_header_id\|>` |
| **ChatML** | Qwen · Phi · Mistral · OpenHermes | `<\|im_start\|>role\ncontent<\|im_end\|>` |
| **Gemma** | gemma2 | `<start_of_turn>role\ncontent<end_of_turn>` |
| **DeepSeek** | deepseek-r1 · deepseek-v2 | `User: ...\nAssistant: <think>` |
| **Llama 2** | llama2 · codellama | `[INST] <<SYS>>\nsystem\n<</SYS>>\nuser [/INST]` |
| **Alpaca** | WizardLM · Vicuna | `### Instruction:\n...\n### Response:` |

---

### 5.6 `agent-demo/workflows/` — Multi-Step Agent Workflows

**EN:** Define and run multi-step agent workflows from JSON — each step can use different models, tools, and conditions.  
**TH:** สร้างและรัน workflow หลาย step จาก JSON — แต่ละ step ใช้โมเดล, tools และเงื่อนไขต่างกันได้

```bash
# รัน research workflow (classify → research → summarize → recommend)
python agent-demo/workflows/workflow_runner.py \
  agent-demo/workflows/examples/research_workflow.json \
  "How does vector search work?"

# รัน RAG Q&A workflow (rephrase → retrieve → answer → evaluate)
python agent-demo/workflows/workflow_runner.py \
  agent-demo/workflows/examples/rag_qa_workflow.json \
  "What is retrieval-augmented generation?"
```

**Workflow structure / โครงสร้าง workflow:**

```json
{
  "name": "My Workflow",
  "steps": [
    {
      "name": "step_name",
      "system": "role prompt",
      "prompt_template": "Do X with: {input} (prev: {prev_output})",
      "model": "claude-haiku-4-5-20251001",
      "tools": ["calculate", "text_search"],
      "condition": "if_prev_success"
    }
  ]
}
```

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
