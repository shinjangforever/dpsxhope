// index.js — จุดเริ่มของ ai-api: ตั้ง Express server, ต่อ route และ middleware แล้วเริ่มฟัง
import 'dotenv/config';                                   // โหลดตัวแปรจากไฟล์ .env เข้า process.env
import express from 'express';
import { chatRouter } from './routes/chat.js';            // route สำหรับ /api/chat
import { rateLimiter } from './middleware/rateLimit.js';  // จำกัดอัตราการเรียก (กัน abuse)

const app = express();
const PORT = process.env.PORT || 3000;   // พอร์ตจาก env ไม่มีก็ใช้ 3000

app.use(express.json());   // แปลง request body เป็น JSON อัตโนมัติ
app.use(rateLimiter);      // บังคับ rate limit ทุก request

app.get('/health', (_req, res) => res.json({ status: 'ok' }));   // endpoint เช็กว่า server ยังมีชีวิต
app.use('/api', chatRouter);                                     // ติด route chat ไว้ใต้ /api

// middleware ดักจับ error รวม — log แล้วตอบ 500 พร้อมข้อความ error
app.use((err, _req, res, _next) => {
  console.error(err.message);
  res.status(500).json({ error: err.message });
});

// เริ่มฟังที่พอร์ตที่กำหนด
app.listen(PORT, () => console.log(`dpsxhope ai-api running on :${PORT}`));
