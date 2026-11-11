"""ทดสอบ python hope.py stack (hopekit/stack.py) ด้วยข้อมูลเครื่องจำลอง ไม่ขึ้นกับเครื่องที่รันทดสอบ"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hopekit import runner, stack  # noqa: E402

ALL_MODULES = runner.PROFILES["all"]["modules"]
OLLAMA = {"models": ["gemma:latest", "plain:latest"], "tool_models": ["gemma:latest"], "knows_tools": True}


class StackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        keep = {k: v for k, v in os.environ.items()
                if k not in ("LLM_PROVIDER", "OLLAMA_MODEL", "OLLAMA_URL", "ANTHROPIC_API_KEY")}
        patcher = unittest.mock.patch.dict(os.environ, keep, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def facts(self, have=("git",), ollama=None, modules=(), env=""):
        (self.root / ".env").write_text(env, encoding="utf-8")
        return stack.collect(
            self.root,
            version_fn=lambda command: f"{command[0]} 1.0" if command[0] in have else None,
            ollama_fn=lambda url: ollama,
            modules_fn=lambda python, names: {name: name in modules for name in names},
        )

    def caps(self, **kwargs):
        return {c["what"]: c for c in stack.capabilities(self.facts(**kwargs))}

    def ready(self, caps, word):
        return next(c for what, c in caps.items() if word in what)

    def test_bare_machine_still_has_the_offline_parts(self):
        caps = self.caps()
        self.assertTrue(self.ready(caps, "robokit")["ready"])
        self.assertTrue(self.ready(caps, "ไม่ใช้ AI")["ready"])
        agent = self.ready(caps, "agent ที่เรียก tool")
        self.assertFalse(agent["ready"])
        self.assertIn("ANTHROPIC_API_KEY", " ".join(agent["missing"]))
        self.assertIn("anthropic", " ".join(agent["missing"]))
        self.assertEqual(self.ready(caps, "Docker")["missing"], ["Docker"])
        self.assertEqual(self.ready(caps, "Go / Rust")["missing"], ["Go", "Rust", "TypeScript"])

    def test_ollama_agent_needs_no_libraries_but_needs_a_tool_model(self):
        caps = self.caps(ollama=OLLAMA, env="LLM_PROVIDER=ollama\nOLLAMA_MODEL=gemma\n")
        self.assertTrue(self.ready(caps, "agent ที่เรียก tool")["ready"])
        self.assertTrue(self.ready(caps, "ขั้นถาม AI")["ready"])

        caps = self.caps(ollama=OLLAMA, env="LLM_PROVIDER=ollama\nOLLAMA_MODEL=plain\n")
        agent = self.ready(caps, "agent ที่เรียก tool")
        self.assertFalse(agent["ready"])
        self.assertIn("gemma:latest", agent["missing"][0])
        self.assertTrue(self.ready(caps, "ขั้นถาม AI")["ready"])          # ถามเฉยๆ ไม่ต้องใช้ tools

        caps = self.caps(ollama=OLLAMA, env="LLM_PROVIDER=ollama\nOLLAMA_MODEL=absent\n")
        self.assertIn("ollama pull absent", self.ready(caps, "ขั้นถาม AI")["missing"][0])
        caps = self.caps(ollama=None, env="LLM_PROVIDER=ollama\n")
        self.assertEqual(self.ready(caps, "ขั้นถาม AI")["missing"], ["เปิด Ollama"])

    def test_old_ollama_without_capabilities_is_not_called_unsupported(self):
        old = {"models": ["plain:latest"], "tool_models": [], "knows_tools": False}
        caps = self.caps(ollama=old, env="LLM_PROVIDER=ollama\nOLLAMA_MODEL=plain\n")
        self.assertTrue(self.ready(caps, "agent ที่เรียก tool")["ready"])

    def test_claude_ready_when_key_and_libraries_exist(self):
        (self.root / "ai-api" / "node_modules").mkdir(parents=True)
        caps = self.caps(have=("git", "node", "npm", "docker", "go", "rustc", "tsc"), modules=ALL_MODULES,
                         env="ANTHROPIC_API_KEY=sk-test\n")
        self.assertEqual([c["what"] for c in caps.values() if not c["ready"]], [])

    def test_report_text_and_json(self):
        lines = []
        kwargs = dict(version_fn=lambda command: None, ollama_fn=lambda url: OLLAMA,
                      modules_fn=lambda python, names: {n: False for n in names})
        (self.root / ".env").write_text("ANTHROPIC_API_KEY=sk-secret-value\n", encoding="utf-8")
        self.assertEqual(stack.report(self.root, say=lines.append, **kwargs), 0)
        text = "\n".join(lines)
        for layer in stack.LAYERS:
            self.assertIn(layer, text)
        self.assertIn("ทำงานอยู่ มี 2 โมเดล", text)
        self.assertIn("https://go.dev/dl/", text)
        self.assertNotIn("sk-secret-value", text)
        lines.clear()
        stack.report(self.root, say=lines.append, as_json=True, **kwargs)
        data = json.loads(lines[0])
        self.assertEqual(set(data), {"tools", "provider", "ollama", "capabilities"})
        self.assertNotIn("sk-secret-value", lines[0])

    def test_command_runs_on_this_machine(self):
        done = subprocess.run([sys.executable, str(ROOT / "hope.py"), "stack", "--json"], capture_output=True,
                              text=True, encoding="utf-8", timeout=120, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["tools"]["python"])

    def test_map_exists_and_names_every_band(self):
        text = (ROOT / "stack" / "README.md").read_text(encoding="utf-8")
        for band in ("AI agent", "งานอัตโนมัติ", "Full stack", "Cybersecurity", "คณิตศาสตร์", "ปรัชญา"):
            self.assertIn(band, text)


if __name__ == "__main__":
    unittest.main()
