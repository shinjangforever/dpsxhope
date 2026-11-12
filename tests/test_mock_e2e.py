"""ทดสอบต้นแบบแบบ end-to-end กับเซิร์ฟเวอร์จำลอง Anthropic (ไม่ใช้ key ไม่ใช้เครือข่ายภายนอก)

ครอบ: agent-kit, workflow, llm-eval (เกณฑ์ผ่าน/ตก), ai-api (auth, CORS, validation)
ไม่ครอบ: คุณภาพคำตอบของโมเดลจริง, Gemini, RAG ที่ต้องโหลด embedding model
"""
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_anthropic import MockAnthropic  # noqa: E402

HAS_SDK = importlib.util.find_spec("anthropic") is not None and importlib.util.find_spec("dotenv") is not None
HAS_API = bool(shutil.which("node")) and (ROOT / "ai-api" / "node_modules").is_dir()


def run(args, cwd, env, timeout=60):
    return subprocess.run(
        [sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=timeout,
    )


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(HAS_SDK, "ต้องติดตั้ง anthropic และ python-dotenv")
class PythonBlueprintsWithMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic().__enter__()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.audit = Path(cls.tmp.name) / "audit.jsonl"
        cls.env = {
            **os.environ,
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_BASE_URL": cls.mock.url,
            "LLM_PROVIDER": "anthropic",        # ไม่ให้ค่าในเครื่องของผู้ทดสอบพาไปเรียก Ollama จริง
            "AGENT_AUDIT_LOG": str(cls.audit),
            "PYTHONIOENCODING": "utf-8",
        }

    @classmethod
    def tearDownClass(cls):
        cls.mock.__exit__()
        cls.tmp.cleanup()

    def test_agent_calls_calculator_and_logs_it(self):
        out = run(["agent.py", "--tools", "calculate", "What is sqrt(65536)?"], ROOT / "agent-kit", self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("256", out.stdout)
        entries = [json.loads(line) for line in self.audit.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(e.get("tool") == "calculate" for e in entries), entries)

    def test_agent_rejects_unknown_tool(self):
        out = run(["agent.py", "--tools", "nope", "x"], ROOT / "agent-kit", self.env)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("nope", out.stdout + out.stderr)

    def test_agent_needs_key(self):
        env = {k: v for k, v in self.env.items() if k != "ANTHROPIC_API_KEY"}
        out = run(["agent.py", "--tools", "calculate", "hi"], ROOT / "agent-kit", {**env, "HOME": self.tmp.name})
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("ANTHROPIC_API_KEY", out.stdout + out.stderr)

    def test_workflow_templates_run_to_completion(self):
        runner = "agent-kit/workflows/workflow_runner.py"
        for name in ("research_workflow.json", "rag_qa_workflow.json"):
            with self.subTest(template=name):
                out = run([runner, f"agent-kit/workflows/templates/{name}", "Explain RAG"], ROOT, self.env)
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertNotIn("✗", out.stdout)

    def test_llm_eval_gate_passes_and_fails(self):
        cases = "examples/cases.example.json"
        ok = run(["evaluator.py", "--cases", cases, "--min-relevance", "0.5"], ROOT / "llm-eval", self.env)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        # mock ให้คะแนนเต็ม 1 จึงตั้งเกณฑ์ faithfulness สูงกว่าเต็มเพื่อบังคับให้ตก
        bad = run(["evaluator.py", "--cases", cases, "--min-faithfulness", "2"], ROOT / "llm-eval", self.env)
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)

    def test_llm_eval_writes_report(self):
        report = Path(self.tmp.name) / "report.json"
        out = run(["evaluator.py", "--cases", "examples/cases.example.json", "--report", str(report)],
                  ROOT / "llm-eval", self.env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(json.loads(report.read_text(encoding="utf-8")))


@unittest.skipUnless(HAS_API, "ต้องมี node และรัน npm ci ใน ai-api ก่อน")
class ApiWithMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic().__enter__()
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = {
            **os.environ,
            "PORT": str(cls.port), "HOST": "127.0.0.1", "APP_API_KEY": "secret",
            "ANTHROPIC_API_KEY": "test-key", "ANTHROPIC_BASE_URL": cls.mock.url,
            "ALLOWED_ORIGINS": "https://app.example", "SYSTEM_PROMPT": "server prompt",
            "ALLOW_CLIENT_SYSTEM": "false",
        }
        cls.proc = subprocess.Popen(
            ["node", "index.js"], cwd=ROOT / "ai-api", env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.5).close()
                return
            except OSError:
                time.sleep(0.2)
        cls.proc.kill()
        raise RuntimeError("ai-api เริ่มไม่ทัน 15 วินาที")

    @classmethod
    def tearDownClass(cls):
        cls.proc.kill()
        cls.proc.wait(timeout=10)
        cls.mock.__exit__()

    def post(self, body, token=None, headers=None):
        req = urllib.request.Request(
            f"{self.base}/api/chat", data=json.dumps(body).encode(), method="POST",
            headers={"content-type": "application/json", **({"authorization": f"Bearer {token}"} if token else {}),
                     **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode()

    def test_requires_bearer_token(self):
        self.assertEqual(self.post({"message": "hi"})[0], 401)
        self.assertEqual(self.post({"message": "hi"}, token="wrong")[0], 401)

    def test_accepts_valid_request(self):
        status, body = self.post({"message": "hi"}, token="secret")
        self.assertEqual(status, 200, body)
        self.assertIn("mock answer", body)

    def test_ignores_client_system_prompt_by_default(self):
        before = len(self.mock.requests)
        self.assertEqual(self.post({"message": "hi", "system": "evil"}, token="secret")[0], 200)
        sent = self.mock.requests[before]
        self.assertNotIn("evil", json.dumps(sent.get("system", "")))
        self.assertIn("server prompt", json.dumps(sent.get("system", "")))

    def test_rejects_bad_input(self):
        self.assertEqual(self.post({"message": 123}, token="secret")[0], 400)

    def test_cors_allowlist(self):
        def allow_origin(origin):
            req = urllib.request.Request(f"{self.base}/api/chat", method="OPTIONS", headers={"origin": origin})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.headers.get("access-control-allow-origin")
        self.assertEqual(allow_origin("https://app.example"), "https://app.example")
        self.assertIsNone(allow_origin("https://evil.example"))

    def test_refuses_public_host_without_key(self):
        env = {**os.environ, "HOST": "0.0.0.0", "PORT": str(free_port()), "APP_API_KEY": ""}
        out = subprocess.run(["node", "index.js"], cwd=ROOT / "ai-api", env=env,
                             capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertNotEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()
