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

## เริ่มใช้งาน

```bash
npm ci
cp ../.env.example ../.env   # ใส่ ANTHROPIC_API_KEY
npm start
```

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "สวัสดี"}'
```

## นำไปใช้จริง

ตั้งค่าใน `.env` หรือระบบ deploy ของคุณ:

| ค่า | หน้าที่ |
|---|---|
| `APP_API_KEY` | บังคับให้ client ส่ง `Authorization: Bearer <key>` |
| `ALLOWED_ORIGINS` | รายชื่อเว็บที่เรียก API ได้ คั่นด้วย comma |
| `SYSTEM_PROMPT` | system prompt ฝั่งเซิร์ฟเวอร์ |
| `ALLOW_CLIENT_SYSTEM` | อนุญาตให้ client ส่ง `system` เอง ค่าเริ่มต้นคือ `false` |
| `RATE_LIMIT_PER_MINUTE` | จำนวนคำขอต่อนาทีต่อ IP |
| `TRUST_PROXY` | จำนวน proxy ที่เชื่อถือ เมื่ออยู่หลัง load balancer |

เซิร์ฟเวอร์ฟังที่ `127.0.0.1` เป็นค่าเริ่มต้น และจะไม่เริ่มบน host อื่นถ้าไม่ได้ตั้ง `APP_API_KEY`

```bash
docker build -t dpsxhope-ai-api .
docker run --rm -p 3000:3000 --env-file ../.env -e HOST=0.0.0.0 dpsxhope-ai-api
```

ต้องตั้ง `APP_API_KEY` ก่อนรันใน container

**ข้อจำกัด:** rate limit เก็บในหน่วยความจำของแต่ละ instance และ `APP_API_KEY` เป็นกุญแจร่วมสำหรับบริการ ไม่ใช่ระบบบัญชีผู้ใช้ ห้ามฝังกุญแจนี้ในเว็บฝั่งผู้ใช้

## เทคโนโลยี

Node.js · Express · Anthropic SDK · Server-Sent Events (SSE)
