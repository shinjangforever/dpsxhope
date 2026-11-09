"""ตรวจว่า "AI ที่ใช้ตอบ" พร้อมใช้งานหรือยัง และบอกวิธีแก้เป็นภาษาไทย"""
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import envfile

DEFAULT_OLLAMA_URL = "http://localhost:11434"


@dataclass(frozen=True)
class Status:
    ok: bool
    text: str
    fix: str = ""


def effective(root: Path, key: str, default: str | None = None) -> str | None:
    """ค่าที่โปรแกรมจะเห็นจริง: environment ก่อน แล้วค่อยไฟล์ .env (ตรงกับ python-dotenv ที่ไม่ทับ environment)"""
    if os.environ.get(key):
        return os.environ[key]
    return envfile.get(root / ".env", key, default)


def ollama_models(url: str = DEFAULT_OLLAMA_URL, timeout: float = 2.0) -> list[str] | None:
    """รายชื่อโมเดลใน Ollama หรือ None ถ้าติดต่อไม่ได้"""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as resp:
            return [m["name"] for m in json.load(resp).get("models", [])]
    except Exception:
        return None


def model_present(models: list[str], wanted: str) -> bool:
    """ชื่อที่ไม่ใส่ tag (เช่น llama3.2) ตรงกับ llama3.2:latest ตามที่ Ollama ทำ"""
    if wanted in models:
        return True
    if ":" not in wanted:
        return f"{wanted}:latest" in models
    return False


def engine_status(root: Path, provider: str | None = None,
                  models_fn: Callable[[str], list[str] | None] = ollama_models) -> Status:
    provider = (provider or effective(root, "LLM_PROVIDER", "anthropic") or "anthropic").lower()
    if provider == "ollama":
        url = effective(root, "OLLAMA_URL", DEFAULT_OLLAMA_URL) or DEFAULT_OLLAMA_URL
        model = effective(root, "OLLAMA_MODEL", "llama3.2") or "llama3.2"
        models = models_fn(url)
        if models is None:
            return Status(False, f"ติดต่อ Ollama ที่ {url} ไม่ได้",
                          "เปิดโปรแกรม Ollama ก่อน หรือดูวิธีติดตั้งที่ https://ollama.com")
        if not model_present(models, model):
            have = ", ".join(models[:5]) or "ยังไม่มีโมเดลเลย"
            return Status(False, f"ไม่พบโมเดล {model} ใน Ollama (มี: {have})",
                          f"ดาวน์โหลดด้วย `ollama pull {model}` หรือเปลี่ยนโมเดลที่เมนูตั้งค่า")
        return Status(True, f"Ollama พร้อม ใช้โมเดล {model}")
    if provider == "anthropic":
        if effective(root, "ANTHROPIC_API_KEY"):
            return Status(True, "Claude พร้อม (ตั้ง API key แล้ว)")
        return Status(False, "ยังไม่ได้ตั้ง ANTHROPIC_API_KEY",
                      "ใส่ key ที่เมนูตั้งค่า หรือรัน: python hope.py config set ANTHROPIC_API_KEY")
    return Status(False, f"ไม่รู้จัก LLM_PROVIDER={provider}",
                  "ตั้งเป็น anthropic หรือ ollama: python hope.py config set LLM_PROVIDER ollama")
