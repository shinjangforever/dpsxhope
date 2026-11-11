"""
agent.py — agent loop พร้อม tool registry, approval และ audit log ใช้ได้ทั้ง Claude และ Ollama

รัน: python agent.py "คำนวณ 2 ยกกำลัง 16"
     python agent.py --tools calculate --system-file my_system.md "คำถาม"

เลือกโมเดลด้วย LLM_PROVIDER=anthropic (ค่าเริ่มต้น ต้องมี ANTHROPIC_API_KEY) หรือ ollama (ในเครื่อง ไม่ต้องมี key)
"""
import argparse
import os
from pathlib import Path

import llm
import tools as registry

llm.load_env()

MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", 8))  # ป้องกัน infinite loop
DEFAULT_SYSTEM = "You are a helpful assistant with access to tools. Use tools when needed."


def run_agent(user_message: str, tool_names: list[str] | None = None, system: str = DEFAULT_SYSTEM,
              max_turns: int = MAX_TURNS) -> str:
    issue = llm.problem()
    if issue:
        raise SystemExit(issue)

    tools = registry.select(tool_names)
    print(f"\n🤖 agent started | {llm.provider()} model={llm.model_name()} | tools={', '.join(tools) or '-'}")
    print(f"👤 user: {user_message}\n")

    try:
        result = llm.tool_loop(
            user_message, tools, registry.run, system=system, max_turns=max_turns,
            on_tool=lambda name, args, out: print(f"  🔧 tool={name} input={args} → {out}"),
        )
    except llm.EngineError as exc:
        raise SystemExit(str(exc))

    if not result.finished:
        print(f"⚠️ ครบ {max_turns} รอบแล้ว agent ยังทำงานไม่จบ (เพิ่มได้ด้วย AGENT_MAX_TURNS)")
        return "agent reached max turns without completing"
    print(f"✅ agent final answer:\n{result.text}")
    return result.text


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
