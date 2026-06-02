"""
agent.py — Claude agent loop ที่ใช้ tool_use จริง (agentic loop)
รัน: python agent.py "คำนวณ 2 ยกกำลัง 16 แล้วหาค่า sqrt ของผลลัพธ์"
"""
import json
import os
import sys

import anthropic
from dotenv import load_dotenv

from tools.calculator import calculate, TOOL_SCHEMA as CALC_SCHEMA
from tools.text_search import text_search, TOOL_SCHEMA as SEARCH_SCHEMA

load_dotenv()

TOOLS = [CALC_SCHEMA, SEARCH_SCHEMA]
TOOL_HANDLERS = {
    "calculate": calculate,
    "text_search": text_search,
}

MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 8  # ป้องกัน infinite loop


def run_agent(user_message: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    messages = [{"role": "user", "content": user_message}]

    print(f"\n🤖 agent started | model={MODEL}")
    print(f"👤 user: {user_message}\n")

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
            system="You are a helpful assistant with access to tools. Use tools when needed.",
        )

        # ถ้า stop_reason = end_turn → agent ตอบเสร็จ
        if response.stop_reason == "end_turn":
            final = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"✅ agent final answer:\n{final}")
            return final

        # ถ้า stop_reason = tool_use → รัน tools แล้วส่งผลกลับ
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                fn = TOOL_HANDLERS.get(block.name)
                if fn is None:
                    result = {"error": f"unknown tool: {block.name}"}
                else:
                    result = fn(**block.input)
                    print(f"  🔧 tool={block.name} input={block.input} → {result}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        break  # stop reason อื่นๆ

    return "agent reached max turns without completing"


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is sqrt(256) + 2^8?"
    run_agent(query)
