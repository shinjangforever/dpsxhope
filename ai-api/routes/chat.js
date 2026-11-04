// chat.js — route คุยกับ Claude: มีทั้งแบบตอบครั้งเดียว และแบบ stream ทีละ token
import { Router } from 'express';
import Anthropic from '@anthropic-ai/sdk';

export const chatRouter = Router();

const MAX_OUTPUT_TOKENS = 2048;
const MAX_MESSAGE_CHARS = 8000;
const modelName = () => process.env.CLAUDE_MODEL || 'claude-haiku-5-5';
const textFrom = (content) => content.filter((block) => block.type === 'text').map((block) => block.text).join('');

const systemPrompt = (requested) => {
  const fallback = process.env.SYSTEM_PROMPT || 'You are a helpful assistant.';
  return process.env.ALLOW_CLIENT_SYSTEM === 'true' && requested ? String(requested) : fallback;
};
const invalidMessage = (message) => typeof message !== 'string' || !message.trim() || message.length > MAX_MESSAGE_CHARS;

// สร้าง client ตอนใช้งาน เพื่อให้ /health ทำงานได้แม้ยังไม่ตั้ง API key
function getClient() {
  if (!process.env.ANTHROPIC_API_KEY) {
    const error = new Error('Set ANTHROPIC_API_KEY in .env at the repo root.');
    error.status = 503;
    throw error;
  }
  return new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
}

// POST /api/chat — ถาม-ตอบครั้งเดียว (ไม่ stream)
chatRouter.post('/chat', async (req, res, next) => {
  try {
    const { message, system, max_tokens = 1024 } = req.body ?? {};
    if (invalidMessage(message)) return res.status(400).json({ error: `message must be 1-${MAX_MESSAGE_CHARS} characters` });

    const response = await getClient().messages.create({
      model: modelName(),
      max_tokens: Math.min(Number(max_tokens) || 1024, MAX_OUTPUT_TOKENS),
      system: systemPrompt(system),
      messages: [{ role: 'user', content: message }],
    });

    res.json({ reply: textFrom(response.content), usage: response.usage, model: response.model });
  } catch (error) {
    next(error);
  }
});

// POST /api/chat/stream — ตอบแบบ stream ผ่าน Server-Sent Events (SSE)
chatRouter.post('/chat/stream', async (req, res, next) => {
  const { message, system } = req.body ?? {};
  if (invalidMessage(message)) return res.status(400).json({ error: `message must be 1-${MAX_MESSAGE_CHARS} characters` });

  let client;
  try {
    client = getClient();
  } catch (error) {
    return next(error);
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');

  try {
    const stream = client.messages.stream({
      model: modelName(),
      max_tokens: 1024,
      system: systemPrompt(system),
      messages: [{ role: 'user', content: message }],
    });

    for await (const chunk of stream) {
      if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
        res.write(`data: ${JSON.stringify({ text: chunk.delta.text })}\n\n`);
      }
    }
    res.write('data: [DONE]\n\n');
  } catch (error) {
    console.error(error.message);
    res.write(`data: ${JSON.stringify({ error: 'stream failed' })}\n\n`);
  }
  res.end();
});
