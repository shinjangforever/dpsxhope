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
pip install -r requirements.txt

# ด้วย Ollama
ollama pull llama3
python ollama_client.py

# ด้วย unified client
python unified_client.py --backend ollama --model llama3
python unified_client.py --backend claude --model claude-haiku-4-5-20251001
```

## engine/controller.py

```bash
python engine/controller.py start llama3
python engine/controller.py bench llama3
python engine/controller.py switch mistral
```

## เทคโนโลยี

Python · Ollama · llama.cpp · Anthropic SDK
