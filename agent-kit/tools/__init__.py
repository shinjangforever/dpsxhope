"""tools — ลงทะเบียน tool อัตโนมัติจากไฟล์ในโฟลเดอร์นี้

เพิ่ม tool โดยคัดลอก _template.py เป็นไฟล์ใหม่ที่ไม่ขึ้นต้นด้วย _
แต่ละไฟล์ต้องมี TOOL_SCHEMA และฟังก์ชันชื่อเดียวกับ TOOL_SCHEMA["name"]
ตั้ง REQUIRES_APPROVAL = True สำหรับ tool ที่แก้ข้อมูลหรือส่งข้อมูลออกนอกเครื่อง
"""
import importlib
import json
import os
import pkgutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

AUDIT_LOG = Path(os.getenv("AGENT_AUDIT_LOG", Path(__file__).resolve().parents[1] / "logs" / "audit.jsonl"))


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict
    handler: Callable
    requires_approval: bool = False


def discover() -> dict[str, Tool]:
    """คืน tool ทั้งหมดในโฟลเดอร์ tools"""
    found: dict[str, Tool] = {}
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        schema = getattr(module, "TOOL_SCHEMA", None)
        if not schema:
            continue
        name = schema["name"]
        found[name] = Tool(name, schema, getattr(module, name), getattr(module, "REQUIRES_APPROVAL", False))
    return found


def select(names: list[str] | None = None) -> dict[str, Tool]:
    """เลือก tool ตามชื่อ และแจ้งทันทีเมื่อชื่อไม่ถูกต้อง"""
    tools = discover()
    if names is None:
        return tools
    missing = sorted(set(names) - set(tools))
    if missing:
        raise SystemExit(f"ไม่พบ tool: {', '.join(missing)}")
    return {name: tools[name] for name in names}


def _approved(tool: Tool, args: dict, preapproved: frozenset = frozenset()) -> bool:
    if not tool.requires_approval or tool.name in preapproved:
        return True
    if not sys.stdin.isatty():
        return False
    return input(f"อนุญาตให้ใช้ {tool.name} ด้วย {args}? [y/N] ").strip().lower() == "y"


AUDIT_MAX_CHARS = 200


def _short(value):
    """ตัดข้อความยาวใน input ก่อนลง log เพื่อไม่ให้เนื้อหาเอกสารทั้งไฟล์ไปค้างใน audit log"""
    if isinstance(value, str) and len(value) > AUDIT_MAX_CHARS:
        return f"{value[:AUDIT_MAX_CHARS]}... [ทั้งหมด {len(value)} ตัวอักษร]"
    if isinstance(value, dict):
        return {k: _short(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(v) for v in value]
    return value


def _audit(name: str, args: dict, result: dict, started: float) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": name,
        "input": _short(args),
        "ok": "error" not in result and result.get("ok", True),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(tools: dict[str, Tool], name: str, args: dict, preapproved: frozenset = frozenset()) -> dict:
    """รัน tool โดยตรวจสิทธิ์ จับ error และบันทึก audit log

    preapproved คือชื่อ tool ที่เจ้าของงานอนุมัติไว้ล่วงหน้า (ใช้กับงานอัตโนมัติที่ไม่มีคนนั่งกด)
    """
    started = time.perf_counter()
    tool = tools.get(name)
    if tool is None:
        result = {"error": f"unknown tool: {name}"}
    elif not isinstance(args, dict):
        result = {"error": "tool input must be an object"}
    elif not _approved(tool, args, preapproved):
        result = {"error": "tool call was not approved"}
    else:
        try:
            result = tool.handler(**args)
        except Exception as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
    _audit(name, args, result, started)
    return result
