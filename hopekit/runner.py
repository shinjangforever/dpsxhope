"""หา Python ที่ติดตั้งไลบรารีครบ สร้าง .venv ติดตั้งไลบรารี และรันโปรแกรมของต้นแบบ"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# โปรไฟล์ที่ผู้ใช้เลือกตอนตั้งค่า: คำอธิบาย ไฟล์ requirements และโมดูลที่ต้อง import ได้
PROFILES = {
    "rag": {
        "label": "ถามตอบจากเอกสารของฉัน",
        "requirements": ["rag-pipeline/requirements.txt"],
        "modules": ["anthropic", "dotenv", "faiss", "sentence_transformers", "rank_bm25", "pypdf", "numpy", "tqdm"],
        "heavy": True,
    },
    "agent": {
        "label": "ผู้ช่วยที่เรียกเครื่องมือได้ (agent)",
        "requirements": ["agent-kit/requirements.txt"],
        "modules": ["anthropic", "dotenv"],
        "heavy": False,
    },
    "eval": {
        "label": "ตรวจคุณภาพ AI (llm-eval)",
        "requirements": ["llm-eval/requirements.txt"],
        "modules": ["anthropic", "dotenv", "google.genai"],
        "heavy": False,
    },
}
PROFILES["all"] = {
    "label": "ทั้งหมดข้างต้น",
    "requirements": [r for p in ("rag", "agent", "eval") for r in PROFILES[p]["requirements"]],
    "modules": sorted({m for p in ("rag", "agent", "eval") for m in PROFILES[p]["modules"]}),
    "heavy": True,
}


def venv_python_path(root: Path = ROOT) -> Path:
    """ที่อยู่ Python ใน .venv (ยังไม่ได้ตรวจว่ามีอยู่จริง)"""
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_python(root: Path = ROOT) -> Path | None:
    candidate = venv_python_path(root)
    return candidate if candidate.exists() else None


def check_modules(python: str | Path, modules: list[str]) -> dict[str, bool]:
    """ถาม Python ตัวนั้นว่า import โมดูลเหล่านี้ได้ไหม ในครั้งเดียว"""
    code = (
        "import importlib.util as u, json, sys\n"
        "out = {}\n"
        "for m in json.loads(sys.argv[1]):\n"
        "    try:\n"
        "        out[m] = u.find_spec(m) is not None\n"
        "    except Exception:\n"
        "        out[m] = False\n"
        "print(json.dumps(out))\n"
    )
    try:
        done = subprocess.run([str(python), "-c", code, json.dumps(modules)], capture_output=True, text=True, timeout=60)
        return json.loads(done.stdout.strip().splitlines()[-1])
    except Exception:
        return {m: False for m in modules}


def resolve_python(modules: list[str] | None = None, root: Path = ROOT) -> str | None:
    """Python ตัวแรกที่มีโมดูลครบ: .venv ของ repo ก่อน แล้วค่อย Python ที่รัน hope.py อยู่"""
    candidates = []
    venv = venv_python(root)
    if venv:
        candidates.append(str(venv))
    if sys.executable and sys.executable not in candidates:
        candidates.append(sys.executable)
    for candidate in candidates:
        if not modules or all(check_modules(candidate, modules).values()):
            return candidate
    return None


def run(args: list[str], cwd: Path = ROOT, env_extra: dict | None = None, stdin_text: str | None = None) -> int:
    """รันโปรแกรมและให้ผลลัพธ์ขึ้นหน้าจอทันที กด Ctrl+C แล้วจบอย่างสุภาพ
    stdin_text ใช้ป้อนข้อความเข้าโปรแกรมแทนการพิมพ์เอง (เช่นคำถามตัวอย่างของเดโม)"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    try:
        if stdin_text is None:
            return subprocess.run([str(a) for a in args], cwd=str(cwd), env=env).returncode
        return subprocess.run([str(a) for a in args], cwd=str(cwd), env=env, input=stdin_text,
                              text=True, encoding="utf-8").returncode
    except KeyboardInterrupt:
        print()
        return 130
    except FileNotFoundError as exc:
        print(f"เปิดโปรแกรมไม่ได้: {exc}")
        return 127


def install_plan(profile: str, root: Path = ROOT) -> list[list[str]]:
    """คำสั่งที่จะรันเพื่อติดตั้ง (คืนเป็นรายการ เพื่อแสดงก่อนรันและใช้ทดสอบ)"""
    python = venv_python_path(root)
    plan = [] if python.exists() else [[sys.executable, "-m", "venv", str(root / ".venv")]]
    reqs = [arg for item in PROFILES[profile]["requirements"] for arg in ("-r", str(root / item))]
    plan.append([str(python), "-m", "pip", "install", "--disable-pip-version-check", *reqs])
    return plan


def install(profile: str, root: Path = ROOT, runner=run) -> int:
    for step in install_plan(profile, root):
        code = runner(step, cwd=root)
        if code != 0:
            return code
    return 0
