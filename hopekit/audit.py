"""ตรวจไลบรารีที่ติดตั้งว่ามีช่องโหว่ที่รู้แล้วหรือไม่ ด้วย npm audit (ai-api) และ pip-audit (Python)

เครื่องมือทั้งสองเทียบรุ่นที่ติดตั้งกับฐานข้อมูลช่องโหว่สาธารณะ จึงต้องต่ออินเทอร์เน็ต
ผล "ไม่พบ" หมายถึงไม่มีช่องโหว่ที่ถูกรายงานแล้วในรุ่นที่ใช้ ไม่ได้แปลว่าโค้ดปลอดภัย
"""
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import runner

CLEAN, FOUND, SKIPPED, FAILED = "ไม่พบช่องโหว่ที่รู้แล้ว", "พบช่องโหว่", "ข้าม", "ตรวจไม่สำเร็จ"


def _run(args: list, cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)
    return done.returncode, (done.stdout + done.stderr).strip()


def npm_audit(root: Path, run: Callable = _run, which: Callable = shutil.which) -> tuple[str, str]:
    """ตรวจไลบรารีของ ai-api ที่ใช้ตอนรันจริง (ไม่รวมของที่ใช้เฉพาะตอนพัฒนา)"""
    npm = which("npm")
    if not npm:
        return SKIPPED, "ไม่มี npm ในเครื่อง"
    if not (root / "ai-api" / "package-lock.json").is_file():
        return SKIPPED, "ไม่มี ai-api/package-lock.json"
    code, out = run([npm, "audit", "--omit=dev"], root / "ai-api")
    if code == 0:
        return CLEAN, out.splitlines()[-1] if out else ""
    if "vulnerabilit" in out:
        return FOUND, out
    return FAILED, out or "npm audit จบด้วยข้อผิดพลาด (ตรวจการเชื่อมต่ออินเทอร์เน็ต)"


def pip_audit(root: Path, run: Callable = _run, modules: Callable = runner.check_modules) -> tuple[str, str]:
    """ตรวจแพ็กเกจที่ติดตั้งอยู่จริงใน .venv ของคู่มือ (หรือ Python ที่รันอยู่ ถ้ายังไม่มี .venv)"""
    python = runner.venv_python(root) or sys.executable
    if not modules(python, ["pip_audit"]).get("pip_audit"):
        return SKIPPED, f"ยังไม่ได้ติดตั้ง pip-audit ติดตั้งด้วย: \"{python}\" -m pip install pip-audit"
    code, out = run([python, "-m", "pip_audit", "--progress-spinner", "off"], root)
    if code == 0:
        return CLEAN, out.splitlines()[-1] if out else ""
    if "vulnerabilit" in out.lower():
        return FOUND, out
    return FAILED, out or "pip-audit จบด้วยข้อผิดพลาด (ตรวจการเชื่อมต่ออินเทอร์เน็ต)"


def report(root: Path, say: Callable = print, checks: dict | None = None) -> int:
    """คืน 1 ถ้าพบช่องโหว่หรือตรวจไม่สำเร็จ, 0 ถ้าทุกอย่างที่ตรวจได้ไม่พบ (ตัวที่ข้ามไม่นับเป็นผ่านหรือไม่ผ่าน)"""
    checks = checks or {"npm audit (ai-api)": npm_audit, "pip-audit (Python)": pip_audit}
    worst = 0
    ran = 0
    for name, check in checks.items():
        state, detail = check(root)
        say(f"== {name} ==\n  {state}")
        if state in (FOUND, FAILED):
            worst = 1
            say("\n".join("  " + line for line in detail.splitlines()[-40:]))
        elif detail:
            say(f"  {detail}")
        ran += state != SKIPPED
        say("")
    if not ran:
        say("ไม่ได้ตรวจอะไรเลย ติดตั้งเครื่องมือตามข้อความด้านบนก่อน")
    say("ผลนี้บอกแค่ช่องโหว่ที่ถูกรายงานแล้วในรุ่นที่ติดตั้ง ไม่ได้ตรวจโค้ดของคุณเอง")
    return worst
