#!/usr/bin/env python3
"""hope.py — คำสั่งเดียวสำหรับตรวจและทดสอบ dpsxhope (ใช้ไลบรารีมาตรฐานของ Python เท่านั้น)

    python hope.py status            ดูว่าเครื่องนี้พร้อมใช้ต้นแบบไหนบ้าง
    python hope.py list [-v]         รายการต้นแบบและสถานะการทดสอบ
    python hope.py test [ชุด]        ชุด: unit | mock | all (ค่าเริ่มต้น unit)
    python hope.py check-links       ตรวจลิงก์ภายใน repo ในไฟล์ .md
    python hope.py check             check-links + test unit + ตรวจ catalog (ใช้เป็นด่านก่อน push)

ทุกคำสั่งไม่ต้องใช้ API key และไม่ต้องมี Docker
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog.json"
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist"}

# ชุดทดสอบ: unit ไม่ต้องติดตั้งอะไรเพิ่ม (ถ้าไม่มี rank_bm25 จะข้ามข้อที่ต้องใช้)
SUITES = {
    "unit": ["test_blueprints.py", "test_thai_search.py", "test_catalog.py"],
    "mock": ["test_mock_e2e.py"],
}
SUITES["all"] = SUITES["unit"] + SUITES["mock"]

# (ชื่อที่แสดง, ชื่อโมดูลที่ import, ใช้กับ)
PY_DEPS = [
    ("anthropic", "anthropic", "agent-kit, llm-eval, rag-pipeline"),
    ("google-genai", "google.genai", "llm-eval (Gemini)"),
    ("faiss", "faiss", "rag-pipeline"),
    ("sentence-transformers", "sentence_transformers", "rag-pipeline"),
    ("rank-bm25", "rank_bm25", "rag-pipeline"),
    ("pypdf", "pypdf", "rag-pipeline (PDF)"),
]
KEYS = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY"]


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _version(cmd: list[str]) -> str:
    exe = shutil.which(cmd[0])
    if not exe:
        return "ไม่พบ"
    try:
        out = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=10)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return "พบ แต่อ่านเวอร์ชันไม่ได้"


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _env_file_values() -> dict:
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def _ollama(url: str) -> str:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=1.5) as resp:
            names = [m["name"] for m in json.load(resp).get("models", [])]
        return f"ทำงานอยู่ ({len(names)} โมเดล)"
    except Exception:
        return "ไม่ตอบสนอง"


def load_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["modules"]


def cmd_status(_args) -> int:
    print("== เครื่องมือ ==")
    print(f"  python  {sys.version.split()[0]}")
    print(f"  node    {_version(['node', '--version'])}")
    print(f"  git     {_version(['git', '--version'])}")
    print(f"  docker  {'พบ' if shutil.which('docker') else 'ไม่พบ'} (ไม่จำเป็นต่อคำสั่งอื่น)")

    print("\n== ไลบรารี Python ==")
    for label, module, used in PY_DEPS:
        mark = "มี  " if _has_module(module) else "ไม่มี"
        print(f"  {mark}  {label:<22} {used}")
    node_modules = (ROOT / "ai-api" / "node_modules").is_dir()
    print(f"  {'มี  ' if node_modules else 'ไม่มี'}  ai-api/node_modules    ai-api (npm ci)")

    env = _env_file_values()
    print("\n== การตั้งค่า ==")
    print(f"  .env    {'มี' if (ROOT / '.env').exists() else 'ไม่มี (คัดลอกจาก .env.example)'}")
    for key in KEYS:
        have = bool(os.environ.get(key) or env.get(key))
        print(f"  {key:<18} {'ตั้งแล้ว' if have else 'ยังไม่ตั้ง'}")
    provider = os.environ.get("LLM_PROVIDER") or env.get("LLM_PROVIDER") or "anthropic"
    ollama_url = os.environ.get("OLLAMA_URL") or env.get("OLLAMA_URL") or "http://localhost:11434"
    print(f"  LLM_PROVIDER       {provider}")
    print(f"  Ollama             {_ollama(ollama_url)}")

    print("\n== ตอนนี้ทำอะไรได้ ==")
    have_llm = any(os.environ.get(k) or env.get(k) for k in KEYS) or "ทำงานอยู่" in _ollama(ollama_url)
    print(f"  ทดสอบโดยไม่ใช้ key : python hope.py test all")
    print(f"  ถามตอบด้วย LLM จริง: {'พร้อม' if have_llm else 'ต้องตั้ง key หรือเปิด Ollama ก่อน'}")
    return 0


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


_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def broken_links() -> tuple[int, list[str]]:
    checked, bad = 0, []
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
            for target in _LINK.findall(line):
                if re.match(r"^(https?:|mailto:|#)", target):
                    continue
                checked += 1
                path = target.split("#", 1)[0]
                if path and not (md.parent / path).exists():
                    bad.append(f"{md.relative_to(ROOT).as_posix()}:{number} -> {target}")
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


def main(argv=None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(prog="hope.py", description="ตรวจและทดสอบ dpsxhope")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="ดูความพร้อมของเครื่อง").set_defaults(func=cmd_status)
    p_list = sub.add_parser("list", help="รายการต้นแบบ")
    p_list.add_argument("-v", "--verbose", action="store_true")
    p_list.set_defaults(func=cmd_list)
    p_test = sub.add_parser("test", help="รันชุดทดสอบ")
    p_test.add_argument("suite", nargs="?", default="unit", choices=list(SUITES))
    p_test.set_defaults(func=cmd_test)
    sub.add_parser("check-links", help="ตรวจลิงก์ในเอกสาร").set_defaults(func=cmd_check_links)
    sub.add_parser("check", help="ด่านตรวจก่อน push").set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
