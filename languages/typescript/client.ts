/**
 * client.ts — Type-safe LLM client in TypeScript
 * รัน: npx ts-node client.ts
 * หรือ compile: tsc client.ts && node client.js
 */
import Anthropic from "@anthropic-ai/sdk";

// ── Types ─────────────────────────────────────────────────────

interface ChatOptions {
  system?: string;
  maxTokens?: number;
  model?: string;
}

interface ChatResult {
  text: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

interface EvalScore {
  relevance: number;       // 0–1
  faithfulness: number;    // 0–1
  formatOk: boolean;
}

// ── Client ────────────────────────────────────────────────────

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export async function chat(
  prompt: string,
  {
    system = "You are a helpful assistant.",
    maxTokens = 1024,
    model = "claude-haiku-4-5-20251001",
  }: ChatOptions = {}
): Promise<ChatResult> {
  const start = performance.now();

  const response = await client.messages.create({
    model,
    max_tokens: maxTokens,
    system,
    messages: [{ role: "user", content: prompt }],
  });

  return {
    text: (response.content[0] as Anthropic.TextBlock).text,
    inputTokens: response.usage.input_tokens,
    outputTokens: response.usage.output_tokens,
    latencyMs: Math.round(performance.now() - start),
  };
}

// ── Structured output helper ──────────────────────────────────

export async function structuredChat<T>(
  prompt: string,
  schema: string,
  options?: ChatOptions
): Promise<T> {
  const system = `${options?.system ?? "You are a helpful assistant."}\n\nAlways reply with valid JSON matching this schema: ${schema}`;
  const result = await chat(prompt, { ...options, system });
  return JSON.parse(result.text) as T;
}

// ── Streaming ─────────────────────────────────────────────────

export async function streamChat(
  prompt: string,
  onToken: (token: string) => void,
  options?: ChatOptions
): Promise<string> {
  const stream = client.messages.stream({
    model: options?.model ?? "claude-haiku-4-5-20251001",
    max_tokens: options?.maxTokens ?? 1024,
    system: options?.system ?? "You are a helpful assistant.",
    messages: [{ role: "user", content: prompt }],
  });

  let full = "";
  for await (const chunk of stream) {
    if (
      chunk.type === "content_block_delta" &&
      chunk.delta.type === "text_delta"
    ) {
      onToken(chunk.delta.text);
      full += chunk.delta.text;
    }
  }
  return full;
}

// ── Demo ──────────────────────────────────────────────────────

async function main() {
  const prompt = process.argv[2] ?? "What is the key difference between RAG and fine-tuning?";
  console.log(`prompt: ${prompt}\n---`);

  // Single turn
  const result = await chat(prompt);
  console.log(result.text);
  console.log(`\n[in=${result.inputTokens} out=${result.outputTokens} latency=${result.latencyMs}ms]`);

  // Structured output
  type Info = { topic: string; difficulty: string; one_line_summary: string };
  const info = await structuredChat<Info>(
    `Classify this prompt: "${prompt}"`,
    '{"topic": "string", "difficulty": "beginner|intermediate|advanced", "one_line_summary": "string"}'
  );
  console.log("\nstructured:", info);
}

main().catch(console.error);
