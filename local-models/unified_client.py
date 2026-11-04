"""
unified_client.py — interface เดียว รองรับทั้ง cloud และ local LLM
เปลี่ยน provider ด้วย 1 argument โดยไม่แก้ code หลัก

Supported:
  cloud  : anthropic, gemini
  local  : ollama (llama3.2, mistral, gemma2, qwen2.5, phi3, deepseek-r1 ฯลฯ)
  local  : openai-compat (LM Studio, Jan, vLLM ที่ expose OpenAI-compatible API)
"""
from __future__ import annotations
import json
import os
import urllib.request
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class Provider(str, Enum):
    ANTHROPIC    = "anthropic"
    GEMINI       = "gemini"
    OLLAMA       = "ollama"
    OPENAI_COMPAT = "openai-compat"   # LM Studio / Jan / vLLM


@dataclass
class Response:
    text: str
    model: str
    provider: Provider
    input_tokens: int = 0
    output_tokens: int = 0


def chat(
    prompt: str,
    system: str = "You are a helpful assistant.",
    provider: Provider = Provider.OLLAMA,
    model: str | None = None,
    max_tokens: int = 1024,
    base_url: str = "http://localhost:11434",   # สำหรับ local providers
) -> Response:

    match provider:
        case Provider.ANTHROPIC:
            return _anthropic(prompt, system, model or os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"), max_tokens)
        case Provider.GEMINI:
            return _gemini(prompt, system, model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash"), max_tokens)
        case Provider.OLLAMA:
            return _ollama(prompt, system, model or os.getenv("OLLAMA_MODEL", "llama3.2"), base_url)
        case Provider.OPENAI_COMPAT:
            return _openai_compat(prompt, system, model or "local-model", max_tokens, base_url)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


# ── Cloud providers ──────────────────────────────────────────


def _anthropic(prompt: str, system: str, model: str, max_tokens: int) -> Response:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return Response(
        text=resp.content[0].text, model=model, provider=Provider.ANTHROPIC,
        input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
    )


def _gemini(prompt: str, system: str, model: str, max_tokens: int) -> Response:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
    )
    return Response(text=resp.text, model=model, provider=Provider.GEMINI)


# ── Local providers ──────────────────────────────────────────


def _ollama(prompt: str, system: str, model: str, base_url: str) -> Response:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/chat", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    return Response(
        text=data["message"]["content"], model=model, provider=Provider.OLLAMA,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
    )


def _openai_compat(prompt: str, system: str, model: str, max_tokens: int, base_url: str) -> Response:
    """รองรับ LM Studio (port 1234), Jan (port 1337), vLLM ฯลฯ"""
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return Response(
        text=text, model=model, provider=Provider.OPENAI_COMPAT,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )


# ── Demo ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Explain RAG in 2 sentences."

    for prov, model, url in [
        (Provider.OLLAMA, None, os.getenv("OLLAMA_URL", "http://localhost:11434")),
        # (Provider.OPENAI_COMPAT, "local-model", "http://localhost:1234"),  # LM Studio
        # (Provider.ANTHROPIC, None, None),   # ต้องมี ANTHROPIC_API_KEY
    ]:
        print(f"\n[{prov}] {model}")
        try:
            resp = chat(prompt, provider=prov, model=model, base_url=url or "")
            print(f"tokens: in={resp.input_tokens} out={resp.output_tokens}")
            print(resp.text)
        except Exception as e:
            print(f"  error: {e}")
