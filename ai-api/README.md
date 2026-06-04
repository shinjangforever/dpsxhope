# ai-api

REST API สำหรับ LLM ด้วย Node.js + Express — รองรับ streaming และ multi-model

## สถาปัตยกรรม

```
index.js           — Express server entry point
routes/            — API route handlers
  chat.js          — /api/chat (stream + non-stream)
middleware/        — auth, rate-limit, logging
```

## Endpoints

```
POST /api/chat          — chat completion (JSON response)
POST /api/chat/stream   — chat completion (SSE streaming)
GET  /api/health        — health check
```

## Quick Start

```bash
npm install
export ANTHROPIC_API_KEY=your_key
node index.js
```

## ตัวอย่าง Request

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "สวัสดี", "model": "claude-haiku-4-5-20251001"}'
```

## เทคโนโลยี

Node.js · Express · Anthropic SDK · Server-Sent Events (SSE)
