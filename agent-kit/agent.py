"""
agent.py — Claude agent loop พร้อม tool registry, approval และ audit log

รัน: python agent.py "คำนวณ 2 ยกกำลัง 16"
     python agent.py --tools calculate --system-file my_system.md "คำถาม"
"""
import argparse
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

import tools as registry

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", 8))  # ป้องกัน infinite loop
DEFAULT_SYSTEM = "You are a helpful assistant with access to tools. Use tools when needed."


def _text(content) -> str:
    return "".join(block.text for block in content if getattr(block, "type", None) == "text")


def run_agent(user_message: str, tool_names: list[str] | None = None, system: str = DEFAULT_SYSTEM,
              max_turns: int = MAX_TURNS) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ตั้ง ANTHROPIC_API_KEY ในไฟล์ .env ที่ root ของ repo ก่อน")

    client = anthropic.Anthropic()
    tools = registry.select(tool_names)
    messages = [{"role": "user", "content": user_message}]

    print(f"\n🤖 agent started | model={MODEL} | tools={', '.join(tools) or '-'}")
    print(f"👤 user: {user_message}\n")

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[tool.schema for tool in tools.values()],
            messages=messages,
            system=system,
        )

        if response.stop_reason != "tool_use":
            final = _text(response.content)
            print(f"✅ agent final answer:\n{final}")
            return final

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = registry.run(tools, block.name, block.input)
            print(f"  🔧 tool={block.name} input={block.input} → {result}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
                "is_error": "error" in result,
            })
        messages.append({"role": "user", "content": tool_results})

    return "agent reached max turns without completing"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="รัน agent พร้อม tool ในโฟลเดอร์ tools/")
    parser.add_argument("prompt", nargs="+", help="คำสั่งหรือคำถาม")
    parser.add_argument("--tools", help="ชื่อ tool คั่นด้วย comma ถ้าไม่ระบุจะใช้ทั้งหมด")
    parser.add_argument("--system-file", type=Path, help="ไฟล์ system prompt")
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS)
    args = parser.parse_args()

    selected = args.tools.split(",") if args.tools else None
    system_prompt = args.system_file.read_text(encoding="utf-8") if args.system_file else DEFAULT_SYSTEM
    run_agent(" ".join(args.prompt), selected, system_prompt, args.max_turns)
