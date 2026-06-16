"""
ตัวอย่าง: few-shot prompting — ให้ตัวอย่างผลลัพธ์ก่อนเพื่อชี้ทิศทาง output
เทคนิคนี้ช่วยให้ LLM เข้าใจ format และ tone ที่ต้องการ
โดยไม่ต้อง fine-tune model ใหม่
"""
from client import chat, Provider

SYSTEM = "You are a concise technical writer."

# ตัวอย่าง (shots) ที่ใส่ใน prompt เพื่อชี้ว่าต้องการ output แบบไหน
SHOTS = """
Examples of the output format I want:

Input: "What is a vector database?"
Output: A vector database stores embeddings (high-dimensional arrays) and supports
fast approximate nearest-neighbor search. Used in RAG and semantic search.

Input: "What is prompt caching?"
Output: Prompt caching reuses computed key-value pairs from a previous request,
reducing latency and cost when the same prefix appears repeatedly.

Now answer the following in the same style:
"""

question = "What is an agentic loop in LLM systems?"

prompt = SHOTS + f'\nInput: "{question}"\nOutput:'

resp = chat(prompt=prompt, system=SYSTEM, provider=Provider.ANTHROPIC)
print(f"Question: {question}")
print(f"Answer:   {resp.text.strip()}")
print(f"\nTokens — input: {resp.input_tokens}, output: {resp.output_tokens}")
