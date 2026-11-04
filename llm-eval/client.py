"""
client.py — Unified LLM client สำหรับ Anthropic Claude และ Google Gemini
ใช้แบบ drop-in: เปลี่ยน provider โดยไม่แก้ logic หลัก
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: Provider


def chat(
    prompt: str,
    system: str = "You are a helpful assistant.",
    provider: Provider = Provider.ANTHROPIC,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> LLMResponse:
    """ส่ง prompt ไปยัง LLM และรับ response กลับ"""

    if provider == Provider.ANTHROPIC:
        return _anthropic_chat(prompt, system, model or os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"), max_tokens)

    if provider == Provider.GEMINI:
        return _gemini_chat(prompt, system, model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash"), max_tokens)

    if provider == Provider.OLLAMA:
        return _ollama_chat(prompt, system, model or os.getenv("OLLAMA_MODEL", "llama3.2"), max_tokens)

    raise ValueError(f"Unknown provider: {provider}")


def _anthropic_chat(prompt: str, system: str, model: str, max_tokens: int) -> LLMResponse:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return LLMResponse(
        text=resp.content[0].text,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        model=model,
        provider=Provider.ANTHROPIC,
    )


def _ollama_chat(prompt: str, system: str, model: str, max_tokens: int) -> LLMResponse:
    import json
    import urllib.request

    payload = json.dumps({
        "model": model,
        "stream": False,
        "think": False,
        "options": {"num_predict": max_tokens},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    request = urllib.request.Request(
        f"{os.getenv('OLLAMA_URL', 'http://localhost:11434')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=int(os.getenv("OLLAMA_TIMEOUT", 300))) as response:
        data = json.load(response)
    return LLMResponse(
        text=data["message"]["content"],
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        model=model,
        provider=Provider.OLLAMA,
    )


def _gemini_chat(prompt: str, system: str, model: str, max_tokens: int) -> LLMResponse:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
    )
    text = resp.text
    usage = resp.usage_metadata
    return LLMResponse(
        text=text,
        input_tokens=getattr(usage, "prompt_token_count", 0),
        output_tokens=getattr(usage, "candidates_token_count", 0),
        model=model,
        provider=Provider.GEMINI,
    )
