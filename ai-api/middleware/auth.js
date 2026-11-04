// auth.js — ตรวจ Bearer token เมื่อกำหนด APP_API_KEY
import { createHash, timingSafeEqual } from 'node:crypto';

const digest = (value) => createHash('sha256').update(value).digest();

export function requireApiKey(req, res, next) {
  const expected = process.env.APP_API_KEY;
  if (!expected) return next();

  const token = (req.get('authorization') ?? '').replace(/^Bearer\s+/i, '');
  if (!timingSafeEqual(digest(token), digest(expected))) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  next();
}
