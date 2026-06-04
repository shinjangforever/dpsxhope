// chat.js — route คุยกับ Claude: มีทั้งแบบตอบครั้งเดียว และแบบ stream ทีละ token
import { Router } from 'express';
import Anthropic from '@anthropic-ai/sdk';

export const chatRouter = Router();
// สร้าง client ของ Anthropic ด้วย API key จาก env
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// POST /api/chat — single turn
// POST /api/chat — ถาม-ตอบครั้งเดียว (ไม่ stream)
chatRouter.post('/chat', async (req, res) => {
  // ดึงค่าจาก body พร้อมตั้ง default ให้ system prompt และ max_tokens
  const { message, system = 'You are a helpful assistant.', max_tokens = 1024 } = req.body;

  if (!message) return res.status(400).json({ error: 'message is required' });   // ต้องมีข้อความ

  // เรียก Claude แบบรอผลครบทีเดียว
  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens,
    system,
    messages: [{ role: 'user', content: message }],
  });

  // ส่งกลับเฉพาะข้อความ + ข้อมูล usage/model ให้ฝั่ง client
  res.json({
    reply: response.content[0].text,
    usage: response.usage,
    model: response.model,
  });
});

// POST /api/chat/stream — streaming response
// POST /api/chat/stream — ตอบแบบ stream ผ่าน Server-Sent Events (SSE)
chatRouter.post('/chat/stream', async (req, res) => {
  const { message, system = 'You are a helpful assistant.' } = req.body;
  if (!message) return res.status(400).json({ error: 'message is required' });

  // ตั้ง header ให้เป็น event-stream และห้าม cache
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');

  // เปิด stream กับ Claude
  const stream = client.messages.stream({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 1024,
    system,
    messages: [{ role: 'user', content: message }],
  });

  // วนรับทีละ chunk — ส่งเฉพาะ delta ที่เป็นข้อความออกไปให้ client
  for await (const chunk of stream) {
    if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
      res.write(`data: ${JSON.stringify({ text: chunk.delta.text })}\n\n`);
    }
  }

  res.write('data: [DONE]\n\n');   // สัญญาณว่าจบ stream
  res.end();
});
