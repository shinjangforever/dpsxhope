"""
logger.py — บันทึก LLM requests/responses + token usage
ใช้เพื่อ monitoring และ debugging AI output ใน production
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any

from client import chat, LLMResponse, Provider

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _log(entry: dict) -> None:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def logged_chat(
    prompt: str,
    system: str = "You are a helpful assistant.",
    provider: Provider = Provider.ANTHROPIC,
    model: str | None = None,
    max_tokens: int = 1024,
    tag: str = "general",
) -> LLMResponse:
    """chat() ที่มี logging อัตโนมัติ"""
    start = time.perf_counter()
    resp = chat(prompt, system=system, provider=provider, model=model, max_tokens=max_tokens)
    latency_ms = (time.perf_counter() - start) * 1000

    _log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "provider": resp.provider,
        "model": resp.model,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "latency_ms": round(latency_ms, 1),
        "prompt_preview": prompt[:120],
        "response_preview": resp.text[:200],
    })

    return resp


def show_logs(date: str | None = None, limit: int = 20) -> None:
    """แสดง log ล่าสุด (ใช้ debug ใน terminal)"""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date}.jsonl"

    if not log_file.exists():
        print(f"no logs for {date}")
        return

    lines = log_file.read_text().strip().split("\n")[-limit:]
    for line in lines:
        entry = json.loads(line)
        print(
            f"[{entry['ts'][11:19]}] {entry['model']} | "
            f"in={entry['input_tokens']} out={entry['output_tokens']} | "
            f"{entry['latency_ms']:.0f}ms | tag={entry['tag']}"
        )
