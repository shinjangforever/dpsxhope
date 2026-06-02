# dpsxhope

> Practical AI engineering — RAG pipelines, LLM APIs, and agent workflows built from scratch.

This repository contains production-oriented implementations of core AI engineering patterns.
Each module is self-contained, runnable, and built to demonstrate real understanding — not just framework usage.

---

## Modules

### 1. `rag-pipeline/` — Retrieval-Augmented Generation

A complete RAG system: ingest documents → embed → index → retrieve → generate → evaluate.

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
cp .env.example .env   # add ANTHROPIC_API_KEY

python ingest.py --docs sample_docs/
python query.py "What is RAG?"
python evaluate.py
```

---

### 2. `llm-eval/` — LLM API Client + Output Evaluation

A unified client that works with both Anthropic Claude and Google Gemini,
plus an evaluator that scores LLM output on relevance, faithfulness, and format compliance.

Features:
- Provider-agnostic interface (swap Claude ↔ Gemini without changing logic)
- Structured output extraction
- Faithfulness scoring via LLM-as-judge
- Request logging with token usage tracking

```bash
cd llm-eval
pip install -r requirements.txt

python examples/structured_output.py
```

---

### 3. `agent-demo/` — Claude Agentic Loop (Tool Use)

A working implementation of Claude's tool use API — the agent decides when to call tools
and loops until it reaches a final answer.

Built-in tools:
- `calculate` — safe math expression evaluator (no hallucinated numbers)
- `text_search` — keyword search over local files

```bash
cd agent-demo
pip install -r requirements.txt

python agent.py "What is sqrt(65536) and how many bits is that?"
```

---

## Setup

Each module has its own `requirements.txt`. Create a `.env` file in the module directory:

```env
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...          # only needed for llm-eval Gemini examples
```

Python 3.11+ recommended.

---

## Design Principles

- **No magic** — each file does one thing and is readable end-to-end
- **Production-minded** — token logging, error handling, evaluation built in
- **Provider flexibility** — not locked to a single LLM vendor
- **Minimal dependencies** — only what's actually needed

---

## Skills Demonstrated

| Area | Implementation |
|------|---------------|
| RAG Pipeline | `rag-pipeline/` — full ingest → retrieve → generate cycle |
| LLM API | `llm-eval/client.py` — Anthropic + Gemini unified client |
| Prompt Design | structured output, few-shot, system prompts |
| Agent / Tool Use | `agent-demo/agent.py` — agentic loop with function calling |
| Evaluation | relevance · faithfulness · recall@k |
| Logging / Monitoring | `llm-eval/logger.py` — JSONL logs with token tracking |
| REST API | `ai-api/` — Express.js chat endpoint |

---

## Author

Daranpat Pattarakanpong (Shin)
Strategic optimizer · AI engineer in practice
