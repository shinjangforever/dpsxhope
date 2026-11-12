"""llm.py — ชั้นกลางคุยกับโมเดล ใช้ได้ทั้ง Claude และ Ollama ในเครื่อง

เลือกด้วย LLM_PROVIDER=anthropic หรือ ollama (ค่าเดียวกับที่ rag-pipeline ใช้)
  anthropic  ต้องมี ANTHROPIC_API_KEY และติดตั้งแพ็กเกจ anthropic
  ollama     ไม่ต้องมี key ข้อมูลอยู่ในเครื่อง ต้องใช้โมเดลที่รองรับ tools ถ้าจะให้เรียก tool

ข้อความภายในใช้รูปแบบกลางสามแบบ แล้วแปลงเป็นของแต่ละเจ้าตอนส่ง
  {"role": "user", "content": "..."}
  {"role": "assistant", "text": "...", "tool_calls": [{"id", "name", "input"}]}
  {"role": "tool", "id": "...", "name": "...", "result": {...}}
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class EngineError(RuntimeError):
    """โมเดลใช้ไม่ได้ในตอนนี้ ข้อความบอกวิธีแก้เป็นภาษาไทย"""


@dataclass
class Reply:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    tokens: int = 0
    truncated: bool = False     # คำตอบถูกตัดเพราะถึง max_tokens


def load_env() -> None:
    """อ่านค่าจากไฟล์ .env โดยไม่ทับค่าที่ตั้งใน environment อยู่แล้ว

    ใช้ python-dotenv ถ้ามี ถ้าไม่มีจะอ่านบรรทัด KEY=VALUE ธรรมดาจาก .env ที่ root ของ repo
    (พอสำหรับใช้กับ Ollama โดยไม่ต้องติดตั้งอะไร)
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        path = Path(__file__).resolve().parents[1] / ".env"
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            return
        for line in lines:
            key, sep, value = line.strip().partition("=")
            key, value = key.strip(), value.strip()
            if not sep or not key or key.startswith("#") or key in os.environ:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ[key] = value
        return
    load_dotenv()


def provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "anthropic").strip().lower()


def model_name(model: str | None = None) -> str:
    if model:
        return model
    if provider() == "ollama":
        return os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    return os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL


def problem() -> str | None:
    """คืนข้อความบอกสิ่งที่ยังขาดก่อนเรียกโมเดล หรือ None ถ้าพร้อม (ไม่ได้ลองเรียกจริง)"""
    name = provider()
    if name == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            return ("ตั้ง ANTHROPIC_API_KEY ในไฟล์ .env ที่ root ของ repo ก่อน "
                    "หรือใช้โมเดลในเครื่องด้วย LLM_PROVIDER=ollama")
        return None
    if name == "ollama":
        return None
    return f"ไม่รู้จัก LLM_PROVIDER={name} (ใช้ anthropic หรือ ollama)"


# ---------- แปลงรูปแบบ ----------

def to_anthropic(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks = [{"type": "text", "text": m["text"]}] if m.get("text") else []
            blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
                       for c in m.get("tool_calls", [])]
            out.append({"role": "assistant", "content": blocks})
        else:
            block = {
                "type": "tool_result",
                "tool_use_id": m["id"],
                "content": json.dumps(m["result"], ensure_ascii=False),
                "is_error": "error" in m["result"],
            }
            # ผลของ tool หลายตัวในรอบเดียวต้องอยู่ในข้อความ user เดียวกัน
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


def to_ollama(messages: list[dict], system: str = "") -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            item = {"role": "assistant", "content": m.get("text", "")}
            if m.get("tool_calls"):
                item["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["input"]}}
                                      for c in m["tool_calls"]]
            out.append(item)
        else:
            out.append({"role": "tool", "tool_name": m["name"],
                        "content": json.dumps(m["result"], ensure_ascii=False)})
    return out


def ollama_tools(schemas: list[dict]) -> list[dict]:
    return [{"type": "function", "function": {
        "name": s["name"], "description": s.get("description", ""), "parameters": s["input_schema"]}}
        for s in schemas]


# ---------- เรียกโมเดล ----------

def _chat_anthropic(messages, system, schemas, max_tokens, model) -> Reply:
    try:
        import anthropic
    except ImportError as exc:
        raise EngineError("ยังไม่ได้ติดตั้งแพ็กเกจ anthropic (pip install -r requirements.txt)") from exc
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": to_anthropic(messages)}
    if system:
        kwargs["system"] = system
    if schemas:
        kwargs["tools"] = schemas
    resp = anthropic.Anthropic().messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    calls = [{"id": b.id, "name": b.name, "input": b.input}
             for b in resp.content if getattr(b, "type", None) == "tool_use"]
    return Reply(text, calls, resp.usage.input_tokens + resp.usage.output_tokens,
                 truncated=getattr(resp, "stop_reason", None) == "max_tokens")


def _chat_ollama(messages, system, schemas, max_tokens, model) -> Reply:
    url = (os.getenv("OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/") + "/api/chat"
    body = {"model": model, "messages": to_ollama(messages, system), "stream": False,
            "options": {"num_predict": max_tokens}}
    if schemas:
        body["tools"] = ollama_tools(schemas)
    think = os.getenv("OLLAMA_THINK")
    if think:
        body["think"] = think.strip().lower() in ("1", "true", "yes", "on")
    data = _post_ollama(url, body, model)
    message = data.get("message") or {}
    cut_short = not (message.get("content") or "").strip() or data.get("done_reason") == "length"
    if not think and message.get("thinking") and cut_short and not message.get("tool_calls"):
        # โมเดลแบบ thinking ใช้โควตาคำตอบไปกับการคิดจนคำตอบว่างหรือขาดกลางทาง ขอใหม่หนึ่งครั้งโดยปิดการคิด
        data = _post_ollama(url, {**body, "think": False}, model)
    return _reply_from_ollama(data)


def _post_ollama(url: str, body: dict, model: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=float(os.getenv("OLLAMA_TIMEOUT", 600))) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if "does not support tools" in detail:
            raise EngineError(f"โมเดล {model} ใน Ollama ไม่รองรับ tools เลือกโมเดลอื่นด้วย OLLAMA_MODEL "
                              "(ดูโมเดลที่รองรับด้วย: python hope.py stack)") from exc
        if exc.code == 404:
            raise EngineError(f"ไม่พบโมเดล {model} ใน Ollama ดาวน์โหลดด้วย `ollama pull {model}`") from exc
        raise EngineError(f"Ollama ตอบ HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EngineError(f"ติดต่อ Ollama ที่ {url} ไม่ได้ ({exc}) เปิดโปรแกรม Ollama ก่อน") from exc


def _reply_from_ollama(data: dict) -> Reply:
    message = data.get("message") or {}
    calls = []
    for i, call in enumerate(message.get("tool_calls") or []):
        fn = call.get("function") or {}
        args = fn.get("arguments") or {}
        if isinstance(args, str):               # บางโมเดลส่ง arguments เป็นข้อความ JSON
            try:
                args = json.loads(args)
            except ValueError:
                args = {"_raw": args}
        calls.append({"id": call.get("id") or f"call_{i}", "name": fn.get("name", ""), "input": args})
    tokens = int(data.get("prompt_eval_count") or 0) + int(data.get("eval_count") or 0)
    return Reply(message.get("content") or "", calls, tokens, truncated=data.get("done_reason") == "length")


def chat(messages: list[dict], system: str = "", schemas: list[dict] | None = None,
         max_tokens: int = 1024, model: str | None = None) -> Reply:
    """ส่งบทสนทนาหนึ่งรอบ คืนข้อความและรายการ tool ที่โมเดลขอเรียก"""
    issue = problem()
    if issue:
        raise EngineError(issue)
    fn = _chat_ollama if provider() == "ollama" else _chat_anthropic
    return fn(messages, system, schemas or [], max_tokens, model_name(model))


@dataclass
class LoopResult:
    text: str
    tokens: int
    finished: bool          # False = ครบจำนวนรอบแล้วโมเดลยังขอเรียก tool อยู่
    tool_calls: int = 0


def tool_loop(prompt: str, tools: dict, run_tool: Callable[[dict, str, dict], dict], system: str = "",
              max_turns: int = 8, max_tokens: int = 1024, model: str | None = None,
              on_tool: Callable[[str, dict, dict], None] | None = None,
              chat_fn: Callable[..., Reply] | None = None) -> LoopResult:
    """วนถามโมเดล รัน tool ที่ขอ แล้วส่งผลกลับ จนโมเดลตอบโดยไม่ขอ tool หรือครบ max_turns

    tools คือ dict ชื่อ -> Tool จาก tools.select() และ run_tool คือ tools.run
    (ตรวจสิทธิ์และเขียน audit log อยู่ในนั้น ชั้นนี้ไม่รัน tool เอง)
    """
    send = chat_fn or chat
    schemas = [tool.schema for tool in tools.values()]
    messages: list[dict] = [{"role": "user", "content": prompt}]
    tokens = calls = 0
    for _ in range(max_turns):
        reply = send(messages, system=system, schemas=schemas, max_tokens=max_tokens, model=model)
        tokens += reply.tokens
        if not reply.tool_calls:
            return LoopResult(reply.text, tokens, True, calls)
        messages.append({"role": "assistant", "text": reply.text, "tool_calls": reply.tool_calls})
        for call in reply.tool_calls:
            result = run_tool(tools, call["name"], call["input"])
            calls += 1
            if on_tool:
                on_tool(call["name"], call["input"], result)
            messages.append({"role": "tool", "id": call["id"], "name": call["name"], "result": result})
    return LoopResult("", tokens, False, calls)
