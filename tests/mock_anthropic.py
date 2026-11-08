"""เซิร์ฟเวอร์จำลอง Anthropic Messages API สำหรับทดสอบโดยไม่ใช้ API key

ใช้กับ SDK จริงผ่าน ANTHROPIC_BASE_URL จึงทดสอบเส้นทางโค้ดจริงทั้งหมด ยกเว้นตัวโมเดล
พฤติกรรม:
  - ถ้าคำขอมี tools และยังไม่มี tool_result  -> ตอบ tool_use เรียก tool ตัวแรก
  - ถ้ามี tool_result แล้ว                      -> ตอบข้อความสุดท้ายที่แนบผลของ tool
  - ถ้าเป็นคำขอแบบ stream                       -> ตอบ SSE "mock stream"
  - ถ้า prompt ขอ JSON (ตัวตรวจของ llm-eval)    -> ตอบ JSON คะแนน 1 ทุกด้าน
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USAGE = {"input_tokens": 12, "output_tokens": 7}
JUDGE_JSON = '{"name":"mock","topic":"rag","relevance":1,"faithfulness":1,"format_ok":true,"notes":"mock"}'


def _message(content, stop_reason):
    return {
        "id": "msg_mock", "type": "message", "role": "assistant", "model": "mock-model",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None, "usage": USAGE,
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_stream(self):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        events = [
            ("message_start", {"type": "message_start", "message": _message([], None)}),
            ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "mock stream"}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 2}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        for name, data in events:
            self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        self.server.requests.append(body)
        if body.get("stream"):
            return self._send_stream()
        last = body["messages"][-1]["content"]
        has_result = isinstance(last, list) and any(b.get("type") == "tool_result" for b in last)
        tools = body.get("tools") or []
        if tools and not has_result:
            tool = tools[0]["name"]
            args = {"expression": "sqrt(65536)"} if tool == "calculate" else {"query": "RAG"}
            return self._send_json(_message(
                [{"type": "tool_use", "id": "toolu_mock", "name": tool, "input": args}], "tool_use"))
        text = "mock answer"
        if has_result:
            text += " " + str(last[0]["content"])[:90]
        if "JSON" in json.dumps(body):
            text = JUDGE_JSON
        self._send_json(_message([{"type": "text", "text": text}], "end_turn"))


class MockAnthropic:
    """ใช้เป็น context manager: with MockAnthropic() as mock: mock.url, mock.requests"""

    def __init__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self._server.requests = []
        self.requests = self._server.requests
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
