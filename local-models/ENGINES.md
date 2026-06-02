# Local LLM Engines / เครื่องยนต์ภาษา Local

คู่มือเปรียบเทียบ engine สำหรับรัน LLM บนเครื่องตัวเอง

---

## เปรียบเทียบ Engine

| Engine | ติดตั้ง | API | GUI | แนะนำสำหรับ |
|--------|---------|-----|-----|------------|
| **Ollama** | ง่ายมาก | `/api/chat` (custom) | ❌ | dev / scripting |
| **LM Studio** | ง่าย | OpenAI-compatible | ✅ | ทดสอบ + API |
| **Jan** | ง่าย | OpenAI-compatible | ✅ | ใช้งานประจำวัน |
| **llama.cpp** | compile เอง | OpenAI-compatible | ❌ | performance สูงสุด |
| **vLLM** | pip install | OpenAI-compatible | ❌ | production serving |
| **Koboldcpp** | ง่าย | custom + OpenAI | ✅ | creative / roleplay |

---

## 1. Ollama (แนะนำสำหรับ dev)

```bash
# ติดตั้ง (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# เปิด server
ollama serve

# ดาวน์โหลดโมเดล
ollama pull llama3.2          # Meta Llama 3.2 3B (เร็ว เล็ก)
ollama pull llama3.1:8b       # Llama 3.1 8B (สมดุล)
ollama pull mistral           # Mistral 7B
ollama pull gemma2:9b         # Google Gemma 2 9B
ollama pull qwen2.5:7b        # Alibaba Qwen 2.5 7B (ภาษาไทยดี)
ollama pull phi3.5            # Microsoft Phi 3.5 (เล็กแต่ฉลาด)
ollama pull deepseek-r1:8b    # DeepSeek R1 8B (reasoning)
ollama pull nomic-embed-text  # Embedding model (ใช้กับ RAG)

# ใช้งาน
ollama run llama3.2 "สวัสดี"
python ollama_client.py "อธิบาย RAG ให้หน่อย"
```

---

## 2. LM Studio (GUI + OpenAI-compatible API)

```
Download: lmstudio.ai
Port default: 1234
Base URL: http://localhost:1234
```

```python
# ใช้กับ unified_client.py
from unified_client import chat, Provider
resp = chat("Hello", provider=Provider.OPENAI_COMPAT, base_url="http://localhost:1234")
```

---

## 3. Jan (GUI + OpenAI-compatible API)

```
Download: jan.ai
Port default: 1337
Base URL: http://localhost:1337
```

---

## 4. llama.cpp (performance สูงสุด)

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && cmake -B build && cmake --build build -j

# รัน server (OpenAI-compatible)
./build/bin/llama-server -m model.gguf --port 8080

# Base URL: http://localhost:8080
```

---

## 5. vLLM (production serving บน GPU)

```bash
pip install vllm

python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.2-3B-Instruct \
  --port 8000

# Base URL: http://localhost:8000
```

---

## โมเดลแนะนำตาม Use Case

| Use Case | โมเดล | Engine |
|----------|--------|--------|
| ภาษาไทย | `qwen2.5:7b` | Ollama |
| Coding | `deepseek-coder-v2` | Ollama |
| Reasoning | `deepseek-r1:8b` | Ollama |
| เร็ว + เล็ก | `phi3.5` `llama3.2` | Ollama |
| RAG embedding | `nomic-embed-text` | Ollama |
| สมดุล | `llama3.1:8b` `mistral` | Ollama / LM Studio |

---

## VRAM Requirements

| VRAM | โมเดลที่รันได้ |
|------|---------------|
| 4 GB | phi3.5, llama3.2 3B, gemma2 2B |
| 8 GB | llama3.1 8B, mistral 7B, qwen2.5 7B |
| 16 GB | llama3.1 70B (Q4), deepseek-r1 14B |
| 24 GB+ | llama3.1 70B full, qwen2.5 72B |

ไม่มี GPU: ใช้ CPU ได้ แต่ช้ากว่า — แนะนำโมเดล 3B–7B
