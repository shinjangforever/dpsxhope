"""ตรวจ stack ของเครื่องนี้: มีภาษาและเครื่องมืออะไร และเปิดใช้ส่วนไหนของคู่มือได้แล้วบ้าง"""
import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import engine, runner


@dataclass(frozen=True)
class Probe:
    key: str
    label: str
    command: tuple
    layer: str
    used_for: str
    get: str            # ที่ติดตั้ง


LAYERS = ["แกนหลัก", "โมเดล", "บริการและข้อมูล", "ภาษาเสริม"]

PROBES = [
    Probe("python", "Python", (), "แกนหลัก", "ทุกอย่างในคู่มือนี้ (ต้อง 3.11 ขึ้นไป)", "https://www.python.org/downloads/"),
    Probe("git", "Git", ("git", "--version"), "แกนหลัก", "ดึงและอัปเดตคู่มือ เก็บประวัติงานของคุณ", "https://git-scm.com/"),
    Probe("ollama", "Ollama", (), "โมเดล", "ถามตอบ agent และงานอัตโนมัติ โดยข้อมูลไม่ออกจากเครื่อง", "https://ollama.com/"),
    Probe("node", "Node.js", ("node", "--version"), "บริการและข้อมูล", "ai-api (เปิด AI เป็นบริการ) และตัวอย่าง TypeScript", "https://nodejs.org/"),
    Probe("npm", "npm", ("npm", "--version"), "บริการและข้อมูล", "ติดตั้งไลบรารีของ ai-api", "https://nodejs.org/"),
    Probe("docker", "Docker", ("docker", "--version"), "บริการและข้อมูล", "ขึ้น stack ตัวอย่างใน languages/yaml (ตรวจแค่ว่าติดตั้ง ไม่ได้ตรวจว่ากำลังรัน)", "https://www.docker.com/"),
    Probe("psql", "PostgreSQL client", ("psql", "--version"), "บริการและข้อมูล", "ใช้ schema ใน languages/sql", "https://www.postgresql.org/download/"),
    Probe("go", "Go", ("go", "version"), "ภาษาเสริม", "ตัวอย่าง languages/go", "https://go.dev/dl/"),
    Probe("rustc", "Rust", ("rustc", "--version"), "ภาษาเสริม", "ตัวอย่าง languages/rust", "https://rustup.rs/"),
    Probe("tsc", "TypeScript", ("tsc", "--version"), "ภาษาเสริม", "ตรวจ type ของ languages/typescript", "https://www.typescriptlang.org/download/"),
    Probe("bash", "Bash", ("bash", "--version"), "ภาษาเสริม", "start.sh และ languages/bash", "https://git-scm.com/ (Windows ได้มากับ Git)"),
]


def run_version(command: tuple, timeout: float = 10) -> str | None:
    """บรรทัดแรกของผลคำสั่ง หรือ None ถ้าไม่มีโปรแกรมหรือรันไม่ผ่าน"""
    exe = shutil.which(command[0])
    if not exe:
        return None
    try:
        done = subprocess.run([exe, *command[1:]], capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stdout or done.stderr).strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def ollama_info(url: str, timeout: float = 2.0) -> dict | None:
    """รายชื่อโมเดลใน Ollama แยกตัวที่รองรับ tools หรือ None ถ้าติดต่อไม่ได้"""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as resp:
            models = json.load(resp).get("models", [])
    except Exception:
        return None
    return {"models": [m["name"] for m in models],
            "tool_models": [m["name"] for m in models if "tools" in (m.get("capabilities") or [])],
            # Ollama รุ่นเก่าไม่ส่ง capabilities มา จึงบอกไม่ได้ว่าโมเดลไหนรองรับ tools
            "knows_tools": any("capabilities" in m for m in models)}


def collect(root: Path, version_fn: Callable = run_version, ollama_fn: Callable = ollama_info,
            modules_fn: Callable = runner.check_modules) -> dict:
    """เก็บข้อเท็จจริงของเครื่องในครั้งเดียว (ทดสอบได้ด้วยการส่งฟังก์ชันจำลองเข้ามา)"""
    tools = {}
    for p in PROBES:
        if p.key == "python":
            tools[p.key] = sys.version.split()[0]
        elif p.key != "ollama":
            tools[p.key] = version_fn(p.command)
    url = engine.effective(root, "OLLAMA_URL", engine.DEFAULT_OLLAMA_URL) or engine.DEFAULT_OLLAMA_URL
    ollama = ollama_fn(url)
    tools["ollama"] = (f"ทำงานอยู่ มี {len(ollama['models'])} โมเดล" if ollama
                       else ("ติดตั้งแล้ว แต่ยังไม่ได้เปิด" if shutil.which("ollama") else None))
    venv = runner.venv_python(root)
    modules = modules_fn(str(venv) if venv else sys.executable, runner.PROFILES["all"]["modules"])
    return {
        "tools": tools,
        "ollama": ollama,
        "ollama_model": engine.effective(root, "OLLAMA_MODEL", "llama3.2"),
        "provider": (engine.effective(root, "LLM_PROVIDER", "anthropic") or "anthropic").lower(),
        "claude_key": bool(engine.effective(root, "ANTHROPIC_API_KEY")),
        "modules": modules,
        "api_installed": (root / "ai-api" / "node_modules").is_dir(),
        "python_ok": sys.version_info >= (3, 11),
    }


def capabilities(facts: dict) -> list[dict]:
    """สิ่งที่ทำได้ตอนนี้ และสิ่งที่ยังขาดของแต่ละอย่าง"""
    t, mods, ollama = facts["tools"], facts["modules"], facts["ollama"]

    def lacking(profile: str) -> list[str]:
        missing = [m for m in runner.PROFILES[profile]["modules"] if not mods.get(m)]
        return [f"ไลบรารี {', '.join(missing)} (python hope.py setup --profile {profile})"] if missing else []

    py = [] if facts["python_ok"] else ["Python 3.11 ขึ้นไป"]
    agent_libs = lacking("agent")
    if facts["provider"] == "ollama":
        agent_libs = []                 # agent และงานอัตโนมัติกับ Ollama ใช้ไลบรารีมาตรฐานอย่างเดียว
        if not ollama:
            model = ["เปิด Ollama"]
        elif not engine.model_present(ollama["models"], facts["ollama_model"]):
            model = [f"โมเดล {facts['ollama_model']} (ollama pull {facts['ollama_model']} หรือเปลี่ยนที่เมนูตั้งค่า)"]
        else:
            model = []
        tool_model = list(model)
        if ollama and not model and ollama["knows_tools"] and not any(
                engine.model_present([name], facts["ollama_model"]) for name in ollama["tool_models"]):
            tool_model = [f"โมเดลที่รองรับ tools ({facts['ollama_model']} ไม่รองรับ"
                          + (f" ตัวที่รองรับในเครื่อง: {', '.join(ollama['tool_models'][:4])})" if ollama["tool_models"]
                             else " และในเครื่องยังไม่มีตัวที่รองรับ)")]
    else:
        model = tool_model = [] if facts["claude_key"] else ["ANTHROPIC_API_KEY หรือเปลี่ยนไปใช้ Ollama (python hope.py setup)"]

    rows = [
        ("เมนูหลัก ตรวจเครื่อง และเครื่องมือหุ่นยนต์ (robokit)", py),
        ("งานอัตโนมัติแบบไม่ใช้ AI (python hope.py auto)", py),
        ("ค้นและถามตอบจากเอกสาร", py + lacking("rag") + model),
        ("agent ที่เรียก tool ได้", py + agent_libs + tool_model),
        ("งานอัตโนมัติที่มีขั้นถาม AI", py + agent_libs + model),
        ("ตรวจคุณภาพ AI (llm-eval)", py + lacking("eval") + ([] if facts["claude_key"] else ["ANTHROPIC_API_KEY"])),
        ("เปิด AI เป็นบริการ (ai-api)", ([] if t.get("node") else ["Node.js"])
         + ([] if facts["api_installed"] else ["npm ci --prefix ai-api"])
         + ([] if facts["claude_key"] else ["ANTHROPIC_API_KEY"])),
        ("ตัวอย่าง Go / Rust / TypeScript", [name for key, name in (("go", "Go"), ("rustc", "Rust"), ("tsc", "TypeScript"))
                                             if not t.get(key)]),
        ("stack ตัวอย่างด้วย Docker", [] if t.get("docker") else ["Docker"]),
    ]
    return [{"what": what, "ready": not missing, "missing": missing} for what, missing in rows]


def report(root: Path, say: Callable = print, as_json: bool = False, **collectors) -> int:
    facts = collect(root, **collectors)
    caps = capabilities(facts)
    if as_json:
        say(json.dumps({"tools": facts["tools"], "provider": facts["provider"],
                        "ollama": facts["ollama"], "capabilities": caps}, ensure_ascii=False, indent=2))
        return 0
    say("stack ของเครื่องนี้ (แผนที่ทั้งหมด: stack/README.md)")
    for layer in LAYERS:
        say(f"\n== {layer} ==")
        for p in (p for p in PROBES if p.layer == layer):
            found = facts["tools"].get(p.key)
            say(f"  {'มี  ' if found else 'ไม่มี'} {p.label:<18} {found or 'ติดตั้งได้ที่ ' + p.get}")
            say(f"        ใช้กับ: {p.used_for}")
        if layer == "โมเดล":
            say(f"  {'มี  ' if facts['claude_key'] else 'ไม่มี'} {'Claude API key':<18} "
                f"{'ตั้งแล้ว' if facts['claude_key'] else 'ตั้งได้ที่ python hope.py config set ANTHROPIC_API_KEY'}")
            say(f"        ตอนนี้ตั้งให้ใช้: {facts['provider']}")
            if facts["ollama"] and facts["ollama"]["knows_tools"]:
                names = facts["ollama"]["tool_models"]
                say(f"        โมเดลใน Ollama ที่รองรับ tools: {', '.join(names[:6]) or 'ยังไม่มี'}")
    say("\n== ทำอะไรได้แล้วบ้าง ==")
    for cap in caps:
        say(f"  {'พร้อม  ' if cap['ready'] else 'ยังขาด'} {cap['what']}")
        for item in cap["missing"]:
            say(f"           - {item}")
    say("\nรายการนี้ตรวจว่ามีเครื่องมือและค่าตั้งครบ ไม่ได้ลองเรียกโมเดลจริง")
    return 0
