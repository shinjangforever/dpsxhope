// index.js — จุดเริ่มของ ai-api: ตั้ง Express server, ต่อ route และ middleware แล้วเริ่มฟัง
import dotenv from 'dotenv';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { chatRouter } from './routes/chat.js';
import { requireApiKey } from './middleware/auth.js';
import { cors } from './middleware/cors.js';
import { createRateLimiter } from './middleware/rateLimit.js';

dotenv.config({ path: fileURLToPath(new URL('../.env', import.meta.url)) });   // ใช้ .env ที่ root ของ repo

const HOST = process.env.HOST || '127.0.0.1';
const PORT = process.env.PORT || 3000;
const isLocal = ['127.0.0.1', 'localhost', '::1'].includes(HOST);

if (!isLocal && !process.env.APP_API_KEY) {
  console.error('Set APP_API_KEY before binding ai-api to a non-local host.');
  process.exit(1);
}

const app = express();
app.disable('x-powered-by');
if (process.env.TRUST_PROXY) app.set('trust proxy', Number(process.env.TRUST_PROXY));

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.use(cors);
app.use(express.json({ limit: '32kb' }));
app.use(createRateLimiter());
app.use('/api', requireApiKey, chatRouter);

// middleware ดักจับ error รวม — log แล้วตอบข้อความที่ไม่เปิดเผยรายละเอียดภายใน
app.use((err, _req, res, _next) => {
  console.error(err.message);
  res.status(err.status || 500).json({ error: err.status === 503 ? err.message : 'Request failed' });
});

app.listen(PORT, HOST, () => console.log(`dpsxhope ai-api running on ${HOST}:${PORT}`));
