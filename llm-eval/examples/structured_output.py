"""
ตัวอย่าง: บังคับให้ LLM ตอบเป็น JSON ที่มี schema ชัดเจน
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client import chat, Provider

SYSTEM = """\
You extract structured information from text.
Always reply with valid JSON only, no markdown, matching this schema exactly:
{"name": "string", "topics": ["string"], "difficulty": "beginner|intermediate|advanced"}
"""

text = """
This course covers advanced RAG techniques including hybrid search,
re-ranking, and query transformation. Students should already know
Python and basic ML concepts.
"""

resp = chat(prompt=f"Extract info from: {text}", system=SYSTEM, provider=Provider.ANTHROPIC)

try:
    data = json.loads(resp.text)
    print("✓ Parsed successfully:")
    print(json.dumps(data, indent=2))
except json.JSONDecodeError:
    print("✗ Failed to parse:", resp.text)
