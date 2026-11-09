#!/usr/bin/env python3
"""hope.py — ตัวเริ่มต้นเดียวสำหรับใช้และตรวจ dpsxhope (ใช้ไลบรารีมาตรฐานของ Python เท่านั้น)

เปิดเมนูภาษาไทย (ไม่ต้องจำคำสั่ง):
    python hope.py                   หรือดับเบิลคลิก start.cmd (Windows) / bash start.sh (macOS, Linux)

คำสั่งตรง:
    python hope.py setup             ตั้งค่าครั้งแรก: ติดตั้งไลบรารี เลือก AI ที่ใช้ตอบ
    python hope.py demo              ลองดูใน 1-2 นาทีด้วยเอกสารตัวอย่าง (ไม่ต้องมี key ก็เห็นส่วนค้นหา)
    python hope.py docs [โฟลเดอร์]   ใส่เอกสาร (ไม่ระบุ = โฟลเดอร์ my-docs, หรือ --sample th)
    python hope.py ask ["คำถาม"]     ถามจากเอกสาร (ไม่ใส่คำถาม = คุยต่อเนื่อง)
    python hope.py agent "งาน"       ให้ agent ทำงาน (ใช้ Claude)
    python hope.py config            ดู/แก้ค่า เช่น config set RAG_TOP_K 6
    python hope.py new-tool ชื่อ     สร้างเครื่องมือใหม่ให้ agent จากแม่แบบ
    python hope.py status            ตรวจเครื่องและบอกขั้นต่อไป

สำหรับผู้พัฒนา:
    python hope.py list [-v]         รายการต้นแบบและสถานะการทดสอบ
    python hope.py test [ชุด]        ชุด: unit | mock | all (ค่าเริ่มต้น unit)
    python hope.py check-links       ตรวจลิงก์และหัวข้อที่ลิงก์ไปถึงในไฟล์ .md
    python hope.py check             check-links + test unit + ตรวจ catalog (ใช้เป็นด่านก่อน push)

ทุกคำสั่งไม่ต้องใช้ API key และไม่ต้องมี Docker ยกเว้นตอนใช้ AI ตอบจริง
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hopekit import commands, menu, runner  # noqa: E402

CATALOG = ROOT / "catalog.json"
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "my-docs"}

# ชุดทดสอบ: unit ไม่ต้องติดตั้งอะไรเพิ่ม (ถ้าไม่มี rank_bm25 จะข้ามข้อที่ต้องใช้)
SUITES = {
    "unit": ["test_blueprints.py", "test_thai_search.py", "test_catalog.py", "test_easy_cli.py", "test_robotics_demo.py"],
    "mock": ["test_mock_e2e.py"],
}
SUITES["all"] = SUITES["unit"] + SUITES["mock"]


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["modules"]


def cmd_list(args) -> int:
    for m in load_catalog():
        print(f"{m['id']:<14} {m['path']:<18} {m['summary']}")
        if args.verbose:
            print(f"{'':<14} รัน        : {m['run']}")
            print(f"{'':<14} ต้องมี     : {', '.join(m['needs']) or '-'}")
            print(f"{'':<14} ทดสอบแล้ว  : {'; '.join(m['verified']) or '-'}")
            print(f"{'':<14} ยังไม่ทดสอบ: {'; '.join(m['unverified']) or '-'}")
    return 0


def run_suite(name: str) -> int:
    if name not in SUITES:
        print(f"ไม่รู้จักชุด '{name}' เลือกได้: {', '.join(SUITES)}")
        return 2
    failed = 0
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1")}
    for pattern in SUITES[name]:
        print(f"\n--- {pattern} ---", flush=True)
        code = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"],
            cwd=ROOT, env=env,
        ).returncode
        failed |= code != 0
    return 1 if failed else 0


def cmd_test(args) -> int:
    return run_suite(args.suite)


# ---------- ตรวจลิงก์ ----------

_MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HTML_LINK = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


def github_slug(heading: str) -> str:
    """รหัสหัวข้อแบบที่ GitHub ใช้: ตัวพิมพ์เล็ก ตัดเครื่องหมายวรรคตอน เว้นวรรคเป็นขีด (เก็บอักษรไทยและวรรณยุกต์)"""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).lower()
    kept = [c for c in text if c in " -_" or unicodedata.category(c)[0] in "LMN"]
    return "".join(kept).replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        match = None if in_fence else _HEADING.match(line)
        if match:
            slug = github_slug(match.group(1))
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def broken_links() -> tuple[int, list[str]]:
    checked, bad = 0, []
    anchor_cache: dict[Path, set[str]] = {}
    for md in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS & set(md.relative_to(ROOT).parts):
            continue
        in_fence = False
        for number, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for target in _MD_LINK.findall(line) + _HTML_LINK.findall(line):
                if re.match(r"^(https?:|mailto:)", target):
                    continue
                checked += 1
                where = f"{md.relative_to(ROOT).as_posix()}:{number} -> {target}"
                raw_path, _, fragment = target.partition("#")
                dest = md if not raw_path else (md.parent / unquote(raw_path))
                if not dest.exists():
                    bad.append(where)
                    continue
                if fragment and dest.suffix == ".md":
                    if dest not in anchor_cache:
                        anchor_cache[dest] = anchors_of(dest)
                    if unquote(fragment).lower() not in anchor_cache[dest]:
                        bad.append(where + "  (ไม่มีหัวข้อนี้)")
    return checked, bad


def cmd_check_links(_args) -> int:
    checked, bad = broken_links()
    for item in bad:
        print(f"ลิงก์เสีย  {item}")
    print(f"ตรวจ {checked} ลิงก์ เสีย {len(bad)}")
    return 1 if bad else 0


def catalog_problems() -> list[str]:
    problems = []
    seen = set()
    for m in load_catalog():
        for key in ("id", "path", "summary", "run", "needs", "verified", "unverified"):
            if key not in m:
                problems.append(f"{m.get('id', '?')}: ขาดฟิลด์ {key}")
        if m.get("id") in seen:
            problems.append(f"id ซ้ำ: {m.get('id')}")
        seen.add(m.get("id"))
        if not (ROOT / m.get("path", "?")).exists():
            problems.append(f"{m.get('id')}: ไม่พบ path {m.get('path')}")
    return problems


def cmd_check(_args) -> int:
    code = 0
    print("== catalog ==")
    problems = catalog_problems()
    for p in problems:
        print(f"  ปัญหา: {p}")
    print(f"  {'ผ่าน' if not problems else 'ไม่ผ่าน'}")
    code |= bool(problems)
    print("\n== ลิงก์ ==")
    code |= cmd_check_links(None)
    print("\n== unit test ==")
    code |= run_suite("unit")
    print("\nสรุป:", "ผ่านทั้งหมด" if not code else "มีข้อที่ไม่ผ่าน")
    return 1 if code else 0


# ---------- คำสั่งสำหรับผู้ใช้ทั่วไป ----------

def cmd_status(_args) -> int:
    return commands.status(commands.Context())


def cmd_menu(_args) -> int:
    return menu.run_menu(commands.Context())


def cmd_setup(args) -> int:
    return commands.setup(commands.Context(), profile=args.profile, engine_name=args.engine,
                          ollama_model=args.ollama_model, yes=args.yes, no_install=args.no_install,
                          dry_run=args.dry_run)


def cmd_demo(_args) -> int:
    return commands.demo(commands.Context())


def cmd_docs(args) -> int:
    return commands.docs(commands.Context(), folder=args.folder, sample=args.sample)


def cmd_ask(args) -> int:
    question = " ".join(args.question).strip() or None
    return commands.ask(commands.Context(), question=question, top_k=args.top_k)


def cmd_agent(args) -> int:
    return commands.agent(commands.Context(), task=" ".join(args.task).strip() or None, tools=args.tools)


def cmd_new_tool(args) -> int:
    return commands.new_tool(commands.Context(), args.name)


def cmd_config(args) -> int:
    ctx = commands.Context()
    action = args.config_command
    if action == "get":
        return commands.config_get(ctx, args.key)
    if action == "set":
        return commands.config_set(ctx, args.key, args.value)
    if action == "unset":
        return commands.config_unset(ctx, args.key)
    return commands.config_list(ctx, show_all=args.all)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hope.py", description="ใช้และตรวจ dpsxhope (ไม่ใส่คำสั่ง = เปิดเมนู)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("menu", help="เปิดเมนูภาษาไทย").set_defaults(func=cmd_menu)
    sub.add_parser("status", help="ตรวจเครื่องและบอกขั้นต่อไป").set_defaults(func=cmd_status)

    p = sub.add_parser("setup", help="ตั้งค่าครั้งแรก")
    p.add_argument("--profile", choices=list(runner.PROFILES), help="สิ่งที่จะใช้ (ไม่ระบุ = ถาม)")
    p.add_argument("--engine", choices=["ollama", "claude", "gemini"], help="AI ที่ใช้ตอบ (ไม่ระบุ = ถาม)")
    p.add_argument("--ollama-model", help="ชื่อโมเดลใน Ollama")
    p.add_argument("-y", "--yes", action="store_true", help="ไม่ถาม ใช้ค่าที่แนะนำ")
    p.add_argument("--no-install", action="store_true", help="ข้ามการติดตั้งไลบรารี ตั้งค่าอย่างเดียว")
    p.add_argument("--dry-run", action="store_true", help="แสดงสิ่งที่จะทำ แต่ไม่เปลี่ยนอะไร")
    p.set_defaults(func=cmd_setup)

    sub.add_parser("demo", help="ลองดูใน 1-2 นาทีด้วยเอกสารตัวอย่าง").set_defaults(func=cmd_demo)

    p = sub.add_parser("docs", help="ใส่เอกสาร (สร้างดัชนีใหม่)")
    p.add_argument("folder", nargs="?", help="โฟลเดอร์เอกสาร (ไม่ระบุ = my-docs)")
    p.add_argument("--sample", choices=["th", "en"], help="ลองกับเอกสารตัวอย่าง")
    p.set_defaults(func=cmd_docs)

    p = sub.add_parser("ask", help="ถามจากเอกสาร (ไม่ใส่คำถาม = คุยต่อเนื่อง)")
    p.add_argument("question", nargs="*", help="คำถาม")
    p.add_argument("--top-k", type=int, help="จำนวนช่วงเอกสารที่ส่งให้ AI อ่าน")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("agent", help="ให้ agent ทำงาน")
    p.add_argument("task", nargs="*", help="งานที่ให้ทำ")
    p.add_argument("--tools", help="ชื่อ tool คั่นด้วย comma (ไม่ระบุ = ใช้ทุกตัว)")
    p.set_defaults(func=cmd_agent)

    p = sub.add_parser("new-tool", help="สร้างเครื่องมือใหม่ให้ agent")
    p.add_argument("name", help="ชื่อ tool เช่น check_stock")
    p.set_defaults(func=cmd_new_tool)

    p = sub.add_parser("config", help="ดูหรือแก้ค่าตั้งต้น")
    p.add_argument("--all", action="store_true", help="แสดงค่าขั้นสูงด้วย")
    p.set_defaults(func=cmd_config, config_command=None)
    csub = p.add_subparsers(dest="config_command")
    g = csub.add_parser("get", help="ดูค่าเดียว")
    g.add_argument("key")
    s = csub.add_parser("set", help="ตั้งค่า (ไม่ใส่ค่า = ถามทีหลัง เหมาะกับ API key เพราะไม่ค้างในประวัติคำสั่ง)")
    s.add_argument("key")
    s.add_argument("value", nargs="?")
    u = csub.add_parser("unset", help="ลบค่าออกจาก .env")
    u.add_argument("key")

    p = sub.add_parser("list", help="รายการต้นแบบ")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("test", help="รันชุดทดสอบ")
    p.add_argument("suite", nargs="?", default="unit", choices=list(SUITES))
    p.set_defaults(func=cmd_test)
    sub.add_parser("check-links", help="ตรวจลิงก์ในเอกสาร").set_defaults(func=cmd_check_links)
    sub.add_parser("check", help="ด่านตรวจก่อน push").set_defaults(func=cmd_check)
    return parser


def main(argv=None) -> int:
    _utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return cmd_menu(args)
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
