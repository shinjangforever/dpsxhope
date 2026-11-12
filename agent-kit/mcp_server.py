"""
mcp_server.py — เปิด tool ในโฟลเดอร์ tools/ ให้แอป AI อื่นใช้ผ่าน Model Context Protocol (MCP) แบบ stdio

  python mcp_server.py                    เปิดทุก tool ที่ไม่ต้องขออนุมัติ
  python mcp_server.py --tools calculate  เปิดเฉพาะที่ระบุ

แอปที่เป็น MCP client จะเป็นผู้เปิดโปรแกรมนี้เอง แล้วคุยกันทาง stdin/stdout ทีละบรรทัด (หนึ่งบรรทัดคือหนึ่งข้อความ JSON-RPC)

ขอบเขตของตัวอย่างนี้ (ตรวจกับสเปกเมื่อ 2026-11-12)
- ทำตามสเปกรุ่น 2025-11-25 และ 2025-06-18 ซึ่งเริ่มด้วยขั้น initialize
- ยังไม่รองรับสเปกรุ่น 2026-07-28 ที่เลิกใช้ initialize แล้วส่งรุ่นมากับทุกคำขอ client รุ่นใหม่ที่ลองถาม server/discover
  จะได้ข้อผิดพลาด "ไม่รู้จัก method" ซึ่งสเปกให้ client ถือว่าเป็น server รุ่นเดิมแล้วกลับไปใช้ initialize
- รองรับ: initialize, ping, tools/list, tools/call ไม่มี resources, prompts และการแบ่งหน้า
- tool ที่ตั้ง REQUIRES_APPROVAL ไม่ถูกเปิดผ่านช่องทางนี้ เพราะไม่มีคนนั่งกดอนุมัติที่ฝั่ง server
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools as registry  # noqa: E402

SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18")
SERVER_INFO = {"name": "dpsxhope-agent-kit", "title": "dpsxhope agent-kit tools", "version": "0.1.0"}
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INVALID_REQUEST = -32600
PARSE_ERROR = -32700


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def exposed(names: list[str] | None = None) -> dict:
    """tool ที่จะเปิดให้ client: ตัดตัวที่ต้องขออนุมัติออกเสมอ"""
    chosen = registry.select(names)
    return {name: tool for name, tool in chosen.items() if not tool.requires_approval}


class Server:
    def __init__(self, tools: dict):
        self.tools = tools

    def initialize(self, params: dict) -> dict:
        wanted = params.get("protocolVersion")
        # สเปก: ถ้ารองรับรุ่นที่ขอให้ตอบรุ่นเดิม ถ้าไม่รองรับให้ตอบรุ่นล่าสุดที่ server รองรับ
        version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": "Tools from the dpsxhope agent-kit. Tools that need human approval are not exposed."}

    def list_tools(self, _params: dict) -> dict:
        return {"tools": [{"name": tool.name, "description": tool.schema.get("description", ""),
                           "inputSchema": tool.schema["input_schema"]} for tool in self.tools.values()]}

    def call_tool(self, params: dict) -> dict:
        name, args = params.get("name"), params.get("arguments", {})
        if name not in self.tools:
            raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
        if not isinstance(args, dict):
            raise RpcError(INVALID_PARAMS, "arguments must be an object")
        result = registry.run(self.tools, name, args)           # ตรวจสิทธิ์และเขียน audit log อยู่ในนี้
        text = json.dumps(result, ensure_ascii=False)
        failed = isinstance(result, dict) and "error" in result
        # ข้อผิดพลาดตอนรัน tool รายงานในผลลัพธ์ด้วย isError ไม่ใช่ข้อผิดพลาดของโปรโตคอล
        return {"content": [{"type": "text", "text": text}], "isError": failed}

    def handle(self, message) -> dict | None:
        """รับข้อความหนึ่งชิ้น คืนคำตอบ หรือ None ถ้าเป็น notification (ไม่ต้องตอบ)"""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
            return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Invalid request")
        if "id" not in message:
            return None                                        # เช่น notifications/initialized
        method, params = message["method"], message.get("params") or {}
        handlers = {"initialize": self.initialize, "ping": lambda _p: {},
                    "tools/list": self.list_tools, "tools/call": self.call_tool}
        try:
            if method not in handlers:
                raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
            if not isinstance(params, dict):
                raise RpcError(INVALID_PARAMS, "params must be an object")
            return {"jsonrpc": "2.0", "id": message["id"], "result": handlers[method](params)}
        except RpcError as exc:
            return _error(message["id"], exc.code, str(exc))


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(server: Server, reader, writer) -> None:
    """อ่านทีละบรรทัดจนปิด stdin (สัญญาณให้จบการทำงาน) แต่ละคำตอบเขียนเป็นหนึ่งบรรทัด"""
    for line in reader:
        line = line.strip()
        if not line:
            continue
        try:
            reply = server.handle(json.loads(line))
        except ValueError:
            reply = _error(None, PARSE_ERROR, "Parse error")
        if reply is not None:
            writer.write(json.dumps(reply, ensure_ascii=False) + "\n")     # json.dumps ไม่ใส่บรรทัดใหม่ในข้อความ
            writer.flush()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MCP server (stdio) สำหรับ tool ของ agent-kit")
    parser.add_argument("--tools", help="ชื่อ tool คั่นด้วย comma ถ้าไม่ระบุจะเปิดทุกตัวที่ไม่ต้องขออนุมัติ")
    args = parser.parse_args(argv)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    tools = exposed(args.tools.split(",") if args.tools else None)
    print(f"dpsxhope MCP server: {', '.join(tools) or 'no tools'}", file=sys.stderr)    # stdout มีได้แต่ข้อความ MCP
    serve(Server(tools), sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
