"""ทดสอบชั้นกลางของ agent-kit (llm.py): แปลงข้อความให้ Claude และ Ollama, วงเรียก tool, และการคุยกับ Ollama จำลอง

ใช้ไลบรารีมาตรฐานอย่างเดียว ไม่เรียกโมเดลจริง
ไม่ครอบ: คุณภาพการเลือก tool ของโมเดลจริง และ Claude API จริง (ส่วน Claude ทดสอบกับเซิร์ฟเวอร์จำลองใน test_mock_e2e.py)
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-kit"))

import llm  # noqa: E402
import tools as registry  # noqa: E402

CALL = {"id": "c1", "name": "calculate", "input": {"expression": "2+2"}}
HISTORY = [
    {"role": "user", "content": "2+2?"},
    {"role": "assistant", "text": "ขอคิดก่อน", "tool_calls": [CALL, {**CALL, "id": "c2"}]},
    {"role": "tool", "id": "c1", "name": "calculate", "result": {"result": 4}},
    {"role": "tool", "id": "c2", "name": "calculate", "result": {"error": "boom"}},
]


class FakeOllama(BaseHTTPRequestHandler):
    """ตอบแบบ Ollama: รอบแรกขอเรียก tool รอบที่มีผลของ tool แล้วตอบข้อความ"""
    mode = "tools"

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(body)
        if self.mode == "no_tools":
            return self._send(400, {"error": "registry.ollama.ai/library/x does not support tools"})
        if self.mode == "missing":
            return self._send(404, {"error": "model not found"})
        if self.mode == "thinking" and body.get("think") is not False:
            return self._send(200, {"message": {"role": "assistant", "content": self.server.partial,
                                                "thinking": "คิดยาวจนหมดโควตา"},
                                    "done_reason": "length", "prompt_eval_count": 1, "eval_count": 1})
        has_result = any(m["role"] == "tool" for m in body["messages"])
        if body.get("tools") and not has_result:
            message = {"role": "assistant", "content": "",
                       "tool_calls": [{"function": {"name": "calculate", "arguments": {"expression": "6*7"}}}]}
        else:
            last = body["messages"][-1]["content"]
            message = {"role": "assistant", "content": f"คำตอบ {last}"}
        self._send(200, {"message": message, "prompt_eval_count": 10, "eval_count": 5})

    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {k: v for k, v in os.environ.items()
               if k not in ("LLM_PROVIDER", "OLLAMA_MODEL", "OLLAMA_URL", "CLAUDE_MODEL", "ANTHROPIC_API_KEY",
                            "OLLAMA_THINK")}
        patcher = unittest.mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = unittest.mock.patch.object(registry, "AUDIT_LOG", Path(self.tmp.name) / "audit.jsonl")
        audit.start()
        self.addCleanup(audit.stop)


class ConvertTest(Base):
    def test_anthropic_groups_tool_results_into_one_user_message(self):
        out = llm.to_anthropic(HISTORY)
        self.assertEqual([m["role"] for m in out], ["user", "assistant", "user"])
        self.assertEqual([b["type"] for b in out[1]["content"]], ["text", "tool_use", "tool_use"])
        results = out[2]["content"]
        self.assertEqual([b["tool_use_id"] for b in results], ["c1", "c2"])
        self.assertEqual([b["is_error"] for b in results], [False, True])

    def test_anthropic_skips_empty_text_block(self):
        out = llm.to_anthropic([{"role": "assistant", "text": "", "tool_calls": [CALL]}])
        self.assertEqual([b["type"] for b in out[0]["content"]], ["tool_use"])

    def test_ollama_shape(self):
        out = llm.to_ollama(HISTORY, system="กติกา")
        self.assertEqual([m["role"] for m in out], ["system", "user", "assistant", "tool", "tool"])
        self.assertEqual(out[2]["tool_calls"][0]["function"], {"name": "calculate", "arguments": {"expression": "2+2"}})
        self.assertEqual(out[3]["tool_name"], "calculate")
        self.assertEqual(json.loads(out[3]["content"]), {"result": 4})
        self.assertEqual(llm.to_ollama(HISTORY)[0]["role"], "user")          # ไม่มี system ก็ไม่ใส่ข้อความว่าง

    def test_ollama_tool_schema(self):
        schema = registry.discover()["calculate"].schema
        fn = llm.ollama_tools([schema])[0]
        self.assertEqual(fn["type"], "function")
        self.assertEqual(fn["function"]["name"], "calculate")
        self.assertEqual(fn["function"]["parameters"], schema["input_schema"])


class ProviderTest(Base):
    def test_default_is_claude_and_needs_key(self):
        self.assertEqual(llm.provider(), "anthropic")
        self.assertIn("ANTHROPIC_API_KEY", llm.problem())
        with self.assertRaises(llm.EngineError):
            llm.chat([{"role": "user", "content": "hi"}])
        os.environ["ANTHROPIC_API_KEY"] = "k"
        self.assertIsNone(llm.problem())

    def test_ollama_needs_no_key_and_unknown_is_refused(self):
        os.environ["LLM_PROVIDER"] = "Ollama"
        self.assertIsNone(llm.problem())
        self.assertEqual(llm.model_name(), llm.DEFAULT_OLLAMA_MODEL)
        os.environ["OLLAMA_MODEL"] = "m1"
        self.assertEqual(llm.model_name(), "m1")
        self.assertEqual(llm.model_name("override"), "override")
        os.environ["LLM_PROVIDER"] = "gpt"
        self.assertIn("gpt", llm.problem())

    def test_load_env_fallback_reads_dotenv_without_overriding(self):
        env = Path(self.tmp.name) / ".env"
        env.write_text('# note\nLLM_PROVIDER=ollama\nOLLAMA_MODEL="m 2"\nCLAUDE_MODEL=from-file\nbroken line\n',
                       encoding="utf-8")
        os.environ["CLAUDE_MODEL"] = "from-env"
        fake_file = Path(self.tmp.name) / "agent-kit" / "llm.py"
        with unittest.mock.patch.object(llm, "__file__", str(fake_file)), \
                unittest.mock.patch.dict(sys.modules, {"dotenv": None}):          # จำลองว่าไม่ได้ติดตั้ง python-dotenv
            llm.load_env()
        self.assertEqual(os.environ["LLM_PROVIDER"], "ollama")
        self.assertEqual(os.environ["OLLAMA_MODEL"], "m 2")
        self.assertEqual(os.environ["CLAUDE_MODEL"], "from-env")


class ToolLoopTest(Base):
    def script(self, *replies):
        replies = list(replies)
        seen = []

        def chat_fn(messages, **kwargs):
            seen.append([dict(m) for m in messages])
            return replies.pop(0)
        return chat_fn, seen

    def test_runs_tool_then_returns_answer(self):
        chat_fn, seen = self.script(llm.Reply("", [CALL], 7), llm.Reply("ได้ 4", [], 3))
        events = []
        tools = registry.select(["calculate"])
        out = llm.tool_loop("2+2?", tools, registry.run, chat_fn=chat_fn,
                            on_tool=lambda name, args, result: events.append((name, result.get("result"))))
        self.assertEqual((out.text, out.tokens, out.finished, out.tool_calls), ("ได้ 4", 10, True, 1))
        self.assertEqual(events, [("calculate", 4)])
        self.assertEqual(seen[1][-1]["role"], "tool")
        self.assertEqual(seen[1][-1]["result"]["result"], 4)

    def test_unknown_tool_is_reported_back_not_executed(self):
        chat_fn, seen = self.script(llm.Reply("", [{"id": "x", "name": "delete_all", "input": {}}]),
                                    llm.Reply("ทำไม่ได้", []))
        out = llm.tool_loop("ลบ", registry.select(["calculate"]), registry.run, chat_fn=chat_fn)
        self.assertTrue(out.finished)
        self.assertIn("unknown tool", seen[1][-1]["result"]["error"])

    def test_stops_at_max_turns(self):
        chat_fn, _ = self.script(*[llm.Reply("", [CALL]) for _ in range(3)])
        out = llm.tool_loop("วน", registry.select(["calculate"]), registry.run, chat_fn=chat_fn, max_turns=3)
        self.assertFalse(out.finished)
        self.assertEqual(out.tool_calls, 3)

    def test_non_object_input_is_refused(self):
        result = registry.run(registry.select(["calculate"]), "calculate", "2+2")
        self.assertIn("error", result)

    def test_audit_log_shortens_long_input(self):
        registry.run(registry.select(["find_lines"]), "find_lines", {"text": "ก" * 5000, "keywords": ["ก"]})
        entry = json.loads(registry.AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-1])
        self.assertLess(len(entry["input"]["text"]), 300)
        self.assertIn("5000", entry["input"]["text"])

    def test_preapproval_is_per_tool(self):
        tool = registry.Tool("pay", {"name": "pay"}, lambda: {"ok": True}, requires_approval=True)
        with unittest.mock.patch.object(sys.stdin, "isatty", return_value=False, create=True):
            self.assertIn("error", registry.run({"pay": tool}, "pay", {}))
            self.assertIn("error", registry.run({"pay": tool}, "pay", {}, frozenset({"other"})))
            self.assertEqual(registry.run({"pay": tool}, "pay", {}, frozenset({"pay"})), {"ok": True})


class OllamaHttpTest(Base):
    def setUp(self):
        super().setUp()
        FakeOllama.mode = "tools"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        self.server.requests = []
        self.server.partial = ""
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        os.environ.update(LLM_PROVIDER="ollama", OLLAMA_MODEL="fake",
                          OLLAMA_URL=f"http://127.0.0.1:{self.server.server_address[1]}")

    def test_full_tool_round_trip(self):
        out = llm.tool_loop("6*7?", registry.select(["calculate"]), registry.run, system="กติกา", max_tokens=99)
        self.assertTrue(out.finished)
        self.assertIn("42", out.text)                    # ผลของ tool ถูกส่งกลับให้โมเดลในรอบที่สอง
        self.assertEqual(out.tokens, 30)
        first, second = self.server.requests
        self.assertEqual(first["model"], "fake")
        self.assertFalse(first["stream"])
        self.assertEqual(first["options"]["num_predict"], 99)
        self.assertEqual(first["messages"][0], {"role": "system", "content": "กติกา"})
        self.assertEqual(first["tools"][0]["function"]["name"], "calculate")
        self.assertEqual(second["messages"][-1]["role"], "tool")
        self.assertNotIn("think", first)
        os.environ["OLLAMA_THINK"] = "false"
        llm.chat([{"role": "user", "content": "hi"}])
        self.assertIs(self.server.requests[-1]["think"], False)

    def test_thinking_model_with_empty_answer_is_asked_again_without_thinking(self):
        FakeOllama.mode = "thinking"
        reply = llm.chat([{"role": "user", "content": "สรุป"}])
        self.assertEqual(reply.text, "คำตอบ สรุป")
        self.assertEqual([r.get("think") for r in self.server.requests], [None, False])
        self.assertFalse(reply.truncated)
        self.server.partial = "- ข้อแรกที่ขาดกลาง"            # คำตอบไม่ว่างแต่ถูกตัด ก็ขอใหม่เช่นกัน
        self.assertEqual(llm.chat([{"role": "user", "content": "สรุป"}]).text, "คำตอบ สรุป")
        self.server.partial = ""
        os.environ["OLLAMA_THINK"] = "true"                 # ผู้ใช้สั่งให้คิด จึงไม่ขอใหม่แทนผู้ใช้
        cut = llm.chat([{"role": "user", "content": "สรุป"}])
        self.assertEqual((cut.text, cut.truncated), ("", True))
        self.assertEqual(len(self.server.requests), 5)

    def test_errors_explain_the_fix(self):
        FakeOllama.mode = "no_tools"
        with self.assertRaisesRegex(llm.EngineError, "ไม่รองรับ tools"):
            llm.chat([{"role": "user", "content": "hi"}], schemas=[registry.discover()["calculate"].schema])
        FakeOllama.mode = "missing"
        with self.assertRaisesRegex(llm.EngineError, "ollama pull fake"):
            llm.chat([{"role": "user", "content": "hi"}])
        os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"
        with self.assertRaisesRegex(llm.EngineError, "ติดต่อ Ollama"):
            llm.chat([{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
