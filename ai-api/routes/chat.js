import { Router } from 'express';
import Anthropic from '@anthropic-ai/sdk';

export const chatRouter = Router();
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// POST /api/chat — single turn
chatRouter.post('/chat', async (req, res) => {
  const { message, system = 'You are a helpful assistant.', max_tokens = 1024 } = req.body;

  if (!message) return res.status(400).json({ error: 'message is required' });

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens,
    system,
    messages: [{ role: 'user', content: message }],
  });

  res.json({
    reply: response.content[0].text,
    usage: response.usage,
    model: response.model,
  });
});

// POST /api/chat/stream — streaming response
chatRouter.post('/chat/stream', async (req, res) => {
  const { message, system = 'You are a helpful assistant.' } = req.body;
  if (!message) return res.status(400).json({ error: 'message is required' });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');

  const stream = client.messages.stream({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 1024,
    system,
    messages: [{ role: 'user', content: message }],
  });

  for await (const chunk of stream) {
    if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
      res.write(`data: ${JSON.stringify({ text: chunk.delta.text })}\n\n`);
    }
  }

  res.write('data: [DONE]\n\n');
  res.end();
});
