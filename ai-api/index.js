import 'dotenv/config';
import express from 'express';
import { chatRouter } from './routes/chat.js';
import { rateLimiter } from './middleware/rateLimit.js';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(rateLimiter);

app.get('/health', (_req, res) => res.json({ status: 'ok' }));
app.use('/api', chatRouter);

app.use((err, _req, res, _next) => {
  console.error(err.message);
  res.status(500).json({ error: err.message });
});

app.listen(PORT, () => console.log(`dpsxhope ai-api running on :${PORT}`));
