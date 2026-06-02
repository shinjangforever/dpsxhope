"""
controller.py — ควบคุม LLM engine: start, stop, status, switch, benchmark
รัน: python controller.py status
     python controller.py start ollama
     python controller.py switch llama3.2 qwen2.5:7b
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EngineType(str, Enum):
    OLLAMA      = "ollama"
    LLAMACPP    = "llamacpp"
    LM_STUDIO   = "lmstudio"
    JAN         = "jan"
    VLLM        = "vllm"


@dataclass
class EngineStatus:
    engine: EngineType
    running: bool
    url: str
    active_model: Optional[str] = None
    loaded_models: list[str] = None
    latency_ms: Optional[int] = None

    def __post_init__(self):
        if self.loaded_models is None:
            self.loaded_models = []


ENGINE_CONFIG = {
    EngineType.OLLAMA:   {"url": "http://localhost:11434", "health": "/api/tags"},
    EngineType.LLAMACPP: {"url": "http://localhost:8080",  "health": "/health"},
    EngineType.LM_STUDIO:{"url": "http://localhost:1234",  "health": "/v1/models"},
    EngineType.JAN:      {"url": "http://localhost:1337",  "health": "/v1/models"},
    EngineType.VLLM:     {"url": "http://localhost:8000",  "health": "/v1/models"},
}


# ── Probe ─────────────────────────────────────────────────────

def probe(engine: EngineType) -> EngineStatus:
    cfg = ENGINE_CONFIG[engine]
    url = cfg["url"]
    try:
        start = time.perf_counter()
        req = urllib.request.Request(f"{url}{cfg['health']}")
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.load(r)
        ms = int((time.perf_counter() - start) * 1000)

        models = []
        if engine == EngineType.OLLAMA:
            models = [m["name"] for m in data.get("models", [])]
        elif engine in (EngineType.LM_STUDIO, EngineType.JAN, EngineType.VLLM):
            models = [m["id"] for m in data.get("data", [])]

        return EngineStatus(engine=engine, running=True, url=url,
                            loaded_models=models, latency_ms=ms)
    except Exception:
        return EngineStatus(engine=engine, running=False, url=url)


def status_all() -> list[EngineStatus]:
    return [probe(e) for e in EngineType]


# ── Start / Stop ──────────────────────────────────────────────

def start_engine(engine: EngineType, model_path: str = "") -> bool:
    if probe(engine).running:
        print(f"[{engine}] already running")
        return True

    if engine == EngineType.OLLAMA:
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif engine == EngineType.LLAMACPP:
        if not model_path:
            print("[llamacpp] model_path required")
            return False
        llamacpp_bin = os.path.expanduser("~/llama.cpp/build/bin/llama-server")
        subprocess.Popen(
            [llamacpp_bin, "-m", model_path, "--port", "8080",
             "-t", str(os.cpu_count() or 4), "--log-disable"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        print(f"[{engine}] start manually via GUI or CLI")
        return False

    # รอ engine ขึ้น
    for _ in range(20):
        time.sleep(0.5)
        if probe(engine).running:
            print(f"[{engine}] started ✓")
            return True
    print(f"[{engine}] failed to start")
    return False


def stop_engine(engine: EngineType) -> None:
    if engine == EngineType.OLLAMA:
        subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True)
    elif engine == EngineType.LLAMACPP:
        subprocess.run(["pkill", "-f", "llama-server"], capture_output=True)
    elif engine == EngineType.VLLM:
        subprocess.run(["pkill", "-f", "vllm.entrypoints"], capture_output=True)
    else:
        print(f"[{engine}] stop manually")
        return
    print(f"[{engine}] stopped")


# ── Model management ──────────────────────────────────────────

def pull_model(model: str) -> None:
    print(f"pulling {model}...")
    subprocess.run(["ollama", "pull", model], check=True)
    print(f"✓ {model} ready")


def switch_model(from_model: str, to_model: str) -> None:
    """unload → pull (ถ้ายังไม่มี) → warm-up"""
    print(f"switching {from_model} → {to_model}")

    # unload current model (Ollama)
    try:
        payload = json.dumps({"model": from_model, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    # ดึงโมเดลใหม่ถ้ายังไม่มี
    status = probe(EngineType.OLLAMA)
    if to_model not in status.loaded_models:
        pull_model(to_model)

    # warm-up
    print(f"warming up {to_model}...")
    payload = json.dumps({
        "model": to_model,
        "prompt": "hi",
        "stream": False,
        "keep_alive": "10m",
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30)
    print(f"✓ {to_model} loaded")


# ── Benchmark ─────────────────────────────────────────────────

def benchmark(model: str, prompt: str = "Reply OK.", n: int = 3) -> dict:
    latencies = []
    for _ in range(n):
        payload = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        latencies.append(int((time.perf_counter() - start) * 1000))

    return {
        "model": model,
        "runs": n,
        "avg_ms": int(sum(latencies) / len(latencies)),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "tokens_per_sec": data.get("eval_count", 0) / max(latencies[-1] / 1000, 0.001),
    }


# ── CLI ───────────────────────────────────────────────────────

def _print_status(s: EngineStatus) -> None:
    icon = "✅" if s.running else "⬜"
    ms   = f"{s.latency_ms}ms" if s.latency_ms else "-"
    models = ", ".join(s.loaded_models[:3]) or "-"
    print(f"  {icon} {s.engine:<12} {s.url:<28} latency={ms:<8} models=[{models}]")


USAGE = """
Usage: python controller.py <command> [args]

Commands:
  status                     — ตรวจสอบทุก engine
  start  <engine> [model]    — เปิด engine (ollama|llamacpp)
  stop   <engine>            — ปิด engine
  pull   <model>             — ดาวน์โหลดโมเดลผ่าน Ollama
  switch <from> <to>         — สลับโมเดล (unload → load)
  bench  <model>             — benchmark latency + tokens/sec

Examples:
  python controller.py status
  python controller.py start ollama
  python controller.py start llamacpp ~/models/llama3.2-Q4.gguf
  python controller.py switch llama3.2 qwen2.5:7b
  python controller.py bench qwen2.5:7b
"""

if __name__ == "__main__":
    args = sys.argv[1:]
    cmd  = args[0] if args else "status"

    if cmd == "status":
        print("\n=== Engine Status ===")
        for s in status_all():
            _print_status(s)

    elif cmd == "start" and len(args) >= 2:
        eng = EngineType(args[1])
        start_engine(eng, args[2] if len(args) > 2 else "")

    elif cmd == "stop" and len(args) >= 2:
        stop_engine(EngineType(args[1]))

    elif cmd == "pull" and len(args) >= 2:
        pull_model(args[1])

    elif cmd == "switch" and len(args) >= 3:
        switch_model(args[1], args[2])

    elif cmd == "bench" and len(args) >= 2:
        result = benchmark(args[1])
        print(json.dumps(result, indent=2))

    else:
        print(USAGE)
