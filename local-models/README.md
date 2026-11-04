# local-models

Local LLM infrastructure — รัน Ollama, llama.cpp, และ unified client สลับโมเดลได้

## สถาปัตยกรรม

```
ollama_client.py   — Ollama API client
unified_client.py  — สลับระหว่าง Ollama / llama.cpp / Claude ด้วย interface เดียว
engine/
  controller.py    — start/stop/switch/bench โมเดล
  chat_format.py   — รองรับ Llama3, ChatML, Gemma, DeepSeek, Alpaca
llamacpp/
  server.sh        — compile และรัน llama.cpp server (multi-arch)
examples/          — ตัวอย่างการใช้งาน
ENGINES.md         — เปรียบเทียบ engine แต่ละตัว
```

## Quick Start

```bash
ollama pull llama3.2
python ollama_client.py "อธิบาย RAG ให้หน่อย"

# เปลี่ยนรุ่นด้วย OLLAMA_MODEL ใน .env
python unified_client.py "Explain embeddings"
```

## engine/controller.py

```bash
python engine/controller.py status
python engine/controller.py start ollama
python engine/controller.py pull llama3.2
python engine/controller.py bench llama3.2
python engine/controller.py switch llama3.2 qwen2.5:7b
```

## เทคโนโลยี

Python · Ollama · llama.cpp · Anthropic SDK
