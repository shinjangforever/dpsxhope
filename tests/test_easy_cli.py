"""ทดสอบชั้นใช้งานง่าย (hopekit + hope.py): ตั้งค่า, ใส่เอกสาร, ถามตอบ, เดโม, config, เมนู, ตัวเปิดสองคลิก

ไม่ติดตั้งไลบรารีหนัก ไม่เรียก AI จริง ใช้ตัวรันปลอมที่จดคำสั่งไว้ และเซิร์ฟเวอร์ Ollama ปลอม
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hope  # noqa: E402
from hopekit import commands, engine, envfile, menu, runner, scaffold, settings  # noqa: E402
from hopekit.ui import Cancelled  # noqa: E402

SECRET_KEYS = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "APP_API_KEY"]


class ScriptedIO:
    """แทนผู้ใช้ด้วยคำตอบที่เตรียมไว้ ถ้าคำตอบหมดจะเหมือนผู้ใช้กด Ctrl+C"""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.out: list[str] = []

    def say(self, text=""):
        self.out.append(str(text))

    def _next(self):
        if not self.answers:
            raise Cancelled()
        return self.answers.pop(0)

    def ask(self, prompt, default=""):
        return self._next() or default

    def secret(self, prompt):
        return self._next()

    def confirm(self, prompt, default=True):
        answer = self._next()
        return default if answer == "" else answer.lower() in {"y", "yes"}

    def choose(self, prompt, options, default=None):
        keys = [k for k, _ in options]
        answer = self._next()
        if answer == "":
            return default if default in keys else keys[0]
        return keys[int(answer) - 1] if answer.isdigit() else answer

    pick = choose

    @property
    def text(self):
        return "\n".join(self.out)


class FakeRun:
    def __init__(self, code=0):
        self.calls = []
        self.code = code

    def __call__(self, args, cwd=None, env_extra=None, stdin_text=None):
        self.calls.append({"args": [str(a) for a in args], "cwd": cwd, "env": env_extra, "stdin": stdin_text})
        return self.code


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy(ROOT / ".env.example", self.root / ".env.example")
        tools = self.root / "agent-kit" / "tools"
        tools.mkdir(parents=True)
        shutil.copy(ROOT / "agent-kit" / "tools" / "_template.py", tools / "_template.py")
        (self.root / "rag-pipeline").mkdir()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for s in settings.SETTINGS:
            os.environ.pop(s.key, None)
        self.addCleanup(self.tmp.cleanup)

    def ctx(self, answers=(), models=None, resolved="PY", code=0):
        self.run_ = FakeRun(code)
        self.io = ScriptedIO(answers)
        return commands.Context(io=self.io, root=self.root, run=self.run_,
                                resolve=lambda modules, root=None: resolved, models_fn=lambda url: models)

    def env_value(self, key):
        return envfile.get(self.root / ".env", key)


class EnvFileTest(Base):
    def test_creates_from_template_and_keeps_comments(self):
        path = self.root / ".env"
        envfile.set_value(path, "ANTHROPIC_API_KEY", "sk-test", template=self.root / ".env.example")
        text = path.read_text(encoding="utf-8")
        self.assertIn("ANTHROPIC_API_KEY=sk-test", text)
        self.assertEqual(text.count("ANTHROPIC_API_KEY="), 1)
        self.assertIn("# ", text)                       # คอมเมนต์จากแม่แบบยังอยู่
        self.assertIn("GEMINI_API_KEY=", text)          # บรรทัดอื่นไม่หาย

    def test_replaces_instead_of_duplicating_and_appends_new_keys(self):
        path = self.root / ".env"
        path.write_text("A=1\n# note\nA=2\nB=3\n", encoding="utf-8")
        envfile.set_value(path, "A", "9")
        envfile.set_value(path, "NEW", "x y")
        self.assertEqual(path.read_text(encoding="utf-8"), 'A=9\n# note\nB=3\n\nNEW="x y"\n')
        self.assertEqual(envfile.read(path), {"A": "9", "B": "3", "NEW": "x y"})

    def test_unset_and_missing_file(self):
        path = self.root / ".env"
        self.assertEqual(envfile.read(path), {})
        self.assertFalse(envfile.unset(path, "A"))
        path.write_text("A=1\nB=2\n", encoding="utf-8")
        self.assertTrue(envfile.unset(path, "A"))
        self.assertEqual(envfile.read(path), {"B": "2"})

    def test_dotenv_expands_dollar_brace_even_when_quoted_so_it_is_refused(self):
        # ตรวจกับ python-dotenv จริง: ${name} ถูกแทนค่าแม้อยู่ในเครื่องหมายคำพูด ส่วน $ เฉยๆ ปลอดภัย
        path = self.root / ".env"
        with self.assertRaises(ValueError):
            envfile.set_value(path, "SYSTEM_PROMPT", "Reply using ${name}")
        envfile.set_value(path, "SYSTEM_PROMPT", "Costs $5 or $HOME")
        self.assertEqual(envfile.get(path, "SYSTEM_PROMPT"), "Costs $5 or $HOME")
        if importlib.util.find_spec("dotenv"):
            from dotenv import dotenv_values
            self.assertEqual(dotenv_values(path)["SYSTEM_PROMPT"], "Costs $5 or $HOME")
            path.write_text("X='a ${missing} b'\n", encoding="utf-8")
            self.assertNotEqual(dotenv_values(path)["X"], "a ${missing} b")      # หลักฐานว่าเครื่องหมายคำพูดไม่ช่วย

    def test_value_with_newline_is_rejected(self):
        with self.assertRaises(ValueError):
            envfile.set_value(self.root / ".env", "A", "line1\nline2")

    def test_quoted_values_round_trip(self):
        path = self.root / ".env"
        for value in ('with space', 'has#hash', 'say "hi"', "back\\slash", ""):
            envfile.set_value(path, "K", value)
            self.assertEqual(envfile.get(path, "K"), value, value)


class SettingsTest(unittest.TestCase):
    def test_valid_values(self):
        self.assertEqual(settings.validate("rag_top_k", " 6 "), "6")
        self.assertEqual(settings.validate("LLM_PROVIDER", "Ollama"), "ollama")
        self.assertEqual(settings.validate("RAG_USE_RERANK", "ใช่"), "true")
        self.assertEqual(settings.validate("ALLOW_CLIENT_SYSTEM", "off"), "false")
        self.assertEqual(settings.validate("ALLOWED_ORIGINS", ""), "")

    def test_invalid_values_explain_why(self):
        for key, bad in (("RAG_TOP_K", "0"), ("RAG_TOP_K", "abc"), ("RAG_TOP_K", "99"), ("LLM_PROVIDER", "gpt"),
                         ("RAG_USE_RERANK", "maybe"), ("OLLAMA_MODEL", "  "), ("ANTHROPIC_API_KEY", ""),
                         ("PORT", "70000"), ("SYSTEM_PROMPT", "a\nb")):
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                settings.validate(key, bad)

    def test_chunk_overlap_must_stay_below_chunk_size(self):
        current = {"RAG_CHUNK_SIZE": "300", "RAG_CHUNK_OVERLAP": "64"}.get
        with self.assertRaises(ValueError):
            settings.validate("RAG_CHUNK_OVERLAP", "300", current)
        with self.assertRaises(ValueError):
            settings.validate("RAG_CHUNK_SIZE", "64", current)
        self.assertEqual(settings.validate("RAG_CHUNK_OVERLAP", "100", current), "100")

    def test_unknown_key_suggests_close_names(self):
        with self.assertRaises(ValueError) as caught:
            settings.find("RAG_TOPK")
        self.assertIn("RAG_TOP_K", str(caught.exception))

    def test_every_setting_has_a_valid_default(self):
        for s in settings.SETTINGS:
            if s.kind == "secret" or s.default == "":
                continue
            with self.subTest(key=s.key):
                self.assertEqual(settings.validate(s.key, s.default), s.default)


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": "llama3.2:latest"}, {"name": "gemma:7b"}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class EngineTest(Base):
    def test_lists_models_from_a_real_http_server(self):
        server = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}"
        self.assertEqual(engine.ollama_models(url), ["llama3.2:latest", "gemma:7b"])

    def test_unreachable_ollama_is_none(self):
        self.assertIsNone(engine.ollama_models("http://127.0.0.1:1", timeout=0.5))

    def test_model_name_matching(self):
        models = ["llama3.2:latest", "gemma:7b"]
        self.assertTrue(engine.model_present(models, "llama3.2"))
        self.assertTrue(engine.model_present(models, "gemma:7b"))
        self.assertFalse(engine.model_present(models, "gemma"))
        self.assertFalse(engine.model_present(models, "qwen"))

    def test_status_for_each_provider(self):
        no_key = engine.engine_status(self.root, "anthropic")
        self.assertFalse(no_key.ok)
        self.assertIn("ANTHROPIC_API_KEY", no_key.fix)
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        self.assertTrue(engine.engine_status(self.root, "anthropic").ok)
        self.assertFalse(engine.engine_status(self.root, "ollama", models_fn=lambda url: None).ok)
        missing = engine.engine_status(self.root, "ollama", models_fn=lambda url: ["other:latest"])
        self.assertFalse(missing.ok)
        self.assertIn("ollama pull", missing.fix)
        os.environ["OLLAMA_MODEL"] = "other"
        self.assertTrue(engine.engine_status(self.root, "ollama", models_fn=lambda url: ["other:latest"]).ok)
        self.assertFalse(engine.engine_status(self.root, "mystery").ok)

    def test_environment_wins_over_env_file(self):
        (self.root / ".env").write_text("RAG_TOP_K=3\n", encoding="utf-8")
        self.assertEqual(engine.effective(self.root, "RAG_TOP_K"), "3")
        os.environ["RAG_TOP_K"] = "7"
        self.assertEqual(engine.effective(self.root, "RAG_TOP_K"), "7")


class ScaffoldTest(Base):
    def test_new_tool_is_importable_and_consistent(self):
        path = scaffold.new_tool("check_stock", self.root / "agent-kit" / "tools")
        spec = importlib.util.spec_from_file_location("check_stock", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.TOOL_SCHEMA["name"], "check_stock")
        self.assertTrue(callable(module.check_stock))
        self.assertEqual(scaffold.existing_tools(self.root / "agent-kit" / "tools"), ["check_stock"])

    def test_rejects_bad_and_duplicate_names(self):
        tools = self.root / "agent-kit" / "tools"
        for bad in ("Check", "1abc", "a", "has space", "../evil", "x" * 41, "_hidden", "check_stock\n"):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                scaffold.new_tool(bad, tools)
        scaffold.new_tool("dup_tool", tools)
        with self.assertRaises(ValueError):
            scaffold.new_tool("dup_tool", tools)

    def test_real_registry_discovers_a_scaffolded_tool(self):
        # ใช้ทะเบียน tool จริงของ agent-kit กับไฟล์ที่สร้างในโฟลเดอร์ชั่วคราว
        sys.path.insert(0, str(ROOT / "agent-kit"))
        os.environ["AGENT_AUDIT_LOG"] = str(self.root / "audit.jsonl")
        import tools as registry
        tools_dir = Path(registry.__file__).parent
        created = scaffold.new_tool("zz_temp_tool", tools_dir)
        self.addCleanup(created.unlink)
        self.assertIn("zz_temp_tool", registry.discover())


class RunnerTest(Base):
    def test_check_and_resolve_python(self):
        found = runner.check_modules(sys.executable, ["json", "definitely_not_installed_xyz"])
        self.assertEqual(found, {"json": True, "definitely_not_installed_xyz": False})
        self.assertEqual(runner.resolve_python(["json"], self.root), sys.executable)
        self.assertIsNone(runner.resolve_python(["definitely_not_installed_xyz"], self.root))

    def test_install_plan_creates_venv_first_then_installs(self):
        plan = runner.install_plan("agent", self.root)
        self.assertEqual(plan[0][1:3], ["-m", "venv"])
        self.assertIn("pip", plan[1])
        self.assertIn(str(self.root / "agent-kit" / "requirements.txt"), plan[1])

    def test_install_plan_skips_venv_when_present(self):
        python = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")
        plan = runner.install_plan("rag", self.root)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], str(python))

    def test_all_profile_is_the_union(self):
        union = set(runner.PROFILES["all"]["modules"])
        for name in ("rag", "agent", "eval"):
            self.assertLessEqual(set(runner.PROFILES[name]["modules"]), union)
        for profile in runner.PROFILES.values():
            for req in profile["requirements"]:
                self.assertTrue((ROOT / req).exists(), req)


class SetupTest(Base):
    def test_dry_run_changes_nothing(self):
        ctx = self.ctx(models=["llama3.2:latest"])
        self.assertEqual(commands.setup(ctx, yes=True, dry_run=True), 0)
        self.assertFalse((self.root / ".env").exists())
        self.assertFalse((self.root / "my-docs").exists())
        self.assertEqual(self.run_.calls, [])
        self.assertIn("คำสั่งติดตั้ง", self.io.text)

    def test_claude_saves_key_without_printing_it(self):
        ctx = self.ctx(answers=["sk-test-123", "y"])
        code = commands.setup(ctx, profile="rag", engine_name="claude", no_install=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.env_value("ANTHROPIC_API_KEY"), "sk-test-123")
        self.assertEqual(self.env_value("LLM_PROVIDER"), "anthropic")
        self.assertNotIn("sk-test-123", self.io.text)
        self.assertIn("Anthropic", self.io.text)               # แจ้งว่าข้อความถูกส่งออกนอกเครื่อง
        self.assertTrue((self.root / "my-docs" / commands.DOCS_README_NAME).exists())

    def test_ollama_picks_a_detected_model_and_installs(self):
        ctx = self.ctx(models=["a:latest", "b:latest"])
        self.assertEqual(commands.setup(ctx, profile="rag", engine_name="ollama", yes=True), 0)
        self.assertEqual(self.env_value("LLM_PROVIDER"), "ollama")
        self.assertEqual(self.env_value("OLLAMA_MODEL"), "a:latest")
        installs = [c["args"] for c in self.run_.calls]
        self.assertTrue(any("pip" in a for a in installs))
        self.assertNotIn("ANTHROPIC_API_KEY", self.io.text.replace("ANTHROPIC_API_KEY=", ""))

    def test_existing_key_is_reused_and_not_asked_again(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-existing"
        ctx = self.ctx(answers=["y"])
        self.assertEqual(commands.setup(ctx, profile="agent", no_install=True), 0)
        self.assertIn("ใช้ค่าเดิม", self.io.text)
        self.assertFalse(self.env_value("ANTHROPIC_API_KEY"))   # ไม่เขียนค่าจาก environment ลงไฟล์ (ในไฟล์ยังว่าง)

    def test_deep_folder_on_windows_is_warned_about_and_can_be_declined(self):
        self.assertTrue(commands.path_too_deep(Path("C:/" + "x" * 80), windows=True))
        self.assertFalse(commands.path_too_deep(Path("C:/dpsxhope"), windows=True))
        self.assertFalse(commands.path_too_deep(Path("/" + "x" * 200), windows=False))
        ctx = self.ctx(answers=["n"], models=["a:latest"])
        with mock.patch.object(commands, "path_too_deep", return_value=True):
            code = commands.setup(ctx, profile="rag", engine_name="ollama", ollama_model="a:latest")
        self.assertEqual(code, 1)
        self.assertIn("ลึกเกินไป", self.io.text)
        self.assertEqual(self.run_.calls, [])
        self.assertFalse((self.root / ".env").exists())
        ctx = self.ctx(models=["a:latest"])                       # โหมด yes ไปต่อได้ (ผู้ใช้ยืนยันแล้ว)
        with mock.patch.object(commands, "path_too_deep", return_value=True):
            self.assertEqual(commands.setup(ctx, profile="rag", engine_name="ollama", yes=True), 0)

    def test_failed_install_stops_before_touching_env(self):
        ctx = self.ctx(code=1, models=["a:latest"])
        self.assertEqual(commands.setup(ctx, profile="rag", engine_name="ollama", yes=True), 1)
        self.assertFalse((self.root / ".env").exists())
        self.assertIn("ติดตั้งไลบรารีไม่สำเร็จ", self.io.text)

    def test_declining_confirmation_changes_nothing(self):
        ctx = self.ctx(answers=["n"], models=["a:latest"])
        self.assertEqual(commands.setup(ctx, profile="rag", engine_name="ollama", ollama_model="a:latest"), 1)
        self.assertEqual(self.run_.calls, [])
        self.assertFalse((self.root / ".env").exists())

    def test_invalid_combinations_are_refused(self):
        self.assertEqual(commands.setup(self.ctx(), profile="agent", engine_name="ollama", yes=True), 2)
        self.assertEqual(commands.setup(self.ctx(), profile="nope", yes=True), 2)
        self.assertEqual(commands.setup(self.ctx(), profile="rag", engine_name="gemini", yes=True), 2)


class DocsAskAgentDemoTest(Base):
    def test_docs_needs_installation_first(self):
        self.assertEqual(commands.docs(self.ctx(resolved=None)), 1)

    def test_docs_rejects_missing_and_empty_folders(self):
        self.assertEqual(commands.docs(self.ctx(), folder=str(self.root / "nope")), 2)
        empty = self.root / "empty"
        empty.mkdir()
        ctx = self.ctx()
        self.assertEqual(commands.docs(ctx, folder=str(empty)), 2)
        self.assertEqual(self.run_.calls, [])
        self.assertIn("--sample th", self.io.text)

    def test_docs_default_folder_and_quoted_path(self):
        ctx = self.ctx()
        self.assertEqual(commands.docs(ctx), 2)                       # my-docs ยังว่าง (มีแต่ README.txt)
        (self.root / "my-docs" / "a.md").write_text("# a\nhello", encoding="utf-8")
        ctx = self.ctx()
        self.assertEqual(commands.docs(ctx), 0)
        call = self.run_.calls[0]
        self.assertEqual(call["args"][1:4], ["pipeline.py", "ingest", "--docs"])
        self.assertEqual(Path(call["args"][4]), self.root / "my-docs")
        ctx = self.ctx()
        self.assertEqual(commands.docs(ctx, folder=f'"{self.root / "my-docs"}"'), 0)   # ลากโฟลเดอร์มาวางจะมีเครื่องหมายคำพูด

    def test_docs_sample_uses_repo_samples(self):
        sample = self.root / "rag-pipeline" / "sample_docs_th"
        sample.mkdir()
        (sample / "x.md").write_text("# x\nhello", encoding="utf-8")
        ctx = self.ctx()
        self.assertEqual(commands.docs(ctx, sample="th"), 0)
        self.assertEqual(Path(self.run_.calls[0]["args"][4]), sample)
        self.assertEqual(commands.docs(self.ctx(), sample="zz"), 2)

    def make_index(self, folder=None):
        folder = folder or self.root / "rag-pipeline" / "data"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index_meta.json").write_text(json.dumps([{"source": "a.md"}, {"source": "b.md"}]), encoding="utf-8")

    def test_ask_preflight_messages(self):
        self.assertEqual(commands.ask(self.ctx(resolved=None), "q"), 1)
        ctx = self.ctx()
        self.assertEqual(commands.ask(ctx, "q"), 1)
        self.assertIn("docs", self.io.text)
        self.make_index()
        ctx = self.ctx()
        self.assertEqual(commands.ask(ctx, "q"), 1)                    # ยังไม่มี key
        self.assertIn("ANTHROPIC_API_KEY", self.io.text)
        self.assertEqual(self.run_.calls, [])

    def test_ask_builds_the_right_command(self):
        self.make_index()
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        ctx = self.ctx()
        self.assertEqual(commands.ask(ctx, "ลาพักร้อนกี่วัน", top_k=6), 0)
        self.assertEqual(self.run_.calls[0]["args"][1:], ["pipeline.py", "query", "ลาพักร้อนกี่วัน", "--top-k", "6"])
        ctx = self.ctx()
        self.assertEqual(commands.ask(ctx), 0)
        self.assertEqual(self.run_.calls[0]["args"][1:], ["pipeline.py", "chat"])

    def test_custom_data_dir_is_respected(self):
        elsewhere = self.root / "elsewhere"
        self.make_index(elsewhere)
        os.environ["RAG_DATA_DIR"] = str(elsewhere)
        self.assertTrue(commands.index_exists(self.ctx()))
        self.assertEqual(commands.index_info(self.ctx()), (2, 2))

    def test_agent_needs_a_key_then_runs_in_agent_kit(self):
        self.assertEqual(commands.agent(self.ctx(), "do it"), 1)
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        ctx = self.ctx()
        self.assertEqual(commands.agent(ctx, "do it", tools="calculate"), 0)
        call = self.run_.calls[0]
        self.assertEqual(call["args"][1:], ["agent.py", "--tools", "calculate", "do it"])
        self.assertEqual(Path(call["cwd"]), self.root / "agent-kit")

    def test_demo_uses_a_separate_index_and_works_without_ai(self):
        ctx = self.ctx()                                               # ยังไม่มี key: ต้องเหลือแค่ส่วนค้นหา
        self.assertEqual(commands.demo(ctx), 0)
        ingest, chat = self.run_.calls
        self.assertIn("ingest", ingest["args"])
        self.assertTrue(ingest["env"]["RAG_DATA_DIR"].endswith("data-demo"))
        self.assertIn("--search-only", chat["args"])
        self.assertEqual(chat["env"]["RAG_DATA_DIR"], ingest["env"]["RAG_DATA_DIR"])
        self.assertEqual(chat["stdin"], "\n".join(commands.DEMO_QUESTIONS) + "\n")
        self.assertFalse((self.root / "rag-pipeline" / "data").exists())

    def test_demo_with_ai_ready_asks_for_answers_and_reuses_index(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        self.make_index(self.root / "rag-pipeline" / "data-demo")
        ctx = self.ctx()
        self.assertEqual(commands.demo(ctx), 0)
        self.assertEqual(len(self.run_.calls), 1)
        self.assertNotIn("--search-only", self.run_.calls[0]["args"])


class ConfigTest(Base):
    def test_set_get_unset(self):
        ctx = self.ctx()
        self.assertEqual(commands.config_set(ctx, "rag_top_k", "6"), 0)
        self.assertEqual(self.env_value("RAG_TOP_K"), "6")
        self.assertEqual(commands.config_unset(ctx, "RAG_TOP_K"), 0)
        self.assertIsNone(self.env_value("RAG_TOP_K"))

    def test_invalid_value_is_refused_and_file_untouched(self):
        ctx = self.ctx()
        self.assertEqual(commands.config_set(ctx, "RAG_TOP_K", "banana"), 2)
        self.assertFalse((self.root / ".env").exists())
        self.assertEqual(commands.config_set(ctx, "NOPE", "1"), 2)

    def test_secret_is_prompted_and_never_shown(self):
        ctx = self.ctx(answers=["sk-secret-999"])
        self.assertEqual(commands.config_set(ctx, "ANTHROPIC_API_KEY"), 0)
        self.assertEqual(self.env_value("ANTHROPIC_API_KEY"), "sk-secret-999")
        commands.config_get(ctx, "ANTHROPIC_API_KEY")
        commands.config_list(ctx, show_all=True)
        self.assertNotIn("sk-secret-999", self.io.text)

    def test_reingest_hint_and_environment_warning(self):
        ctx = self.ctx()
        commands.config_set(ctx, "RAG_CHUNK_SIZE", "800")
        self.assertIn("ใส่เอกสารใหม่", self.io.text)
        os.environ["RAG_TOP_K"] = "2"
        commands.config_set(ctx, "RAG_TOP_K", "5")
        self.assertIn("environment variable", self.io.text)

    def test_list_marks_defaults(self):
        ctx = self.ctx()
        commands.config_list(ctx)
        self.assertIn("RAG_TOP_K", self.io.text)
        self.assertIn("ค่าเริ่มต้น", self.io.text)
        self.assertNotIn("RAG_CHUNK_SIZE", self.io.text)               # ค่าขั้นสูงซ่อนไว้ก่อน


class NextStepAndMenuTest(Base):
    def test_next_step_follows_the_state(self):
        k = commands.MENU_KEYS
        self.assertEqual(commands.next_step(self.ctx(resolved=None))[0], k["setup"])
        self.assertEqual(commands.next_step(self.ctx())[0], k["settings"])
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        self.assertEqual(commands.next_step(self.ctx())[0], k["docs"])
        data = self.root / "rag-pipeline" / "data"
        data.mkdir(parents=True)
        (data / "index_meta.json").write_text("[]", encoding="utf-8")
        self.assertEqual(commands.next_step(self.ctx())[0], k["ask"])

    def test_menu_exits_on_zero_and_runs_status(self):
        ctx = self.ctx(answers=["0"])
        self.assertEqual(menu.run_menu(ctx), 0)
        self.assertIn("ขั้นต่อไปที่แนะนำ", self.io.text)
        ctx = self.ctx(answers=[commands.MENU_KEYS["status"], "", "0"])
        self.assertEqual(menu.run_menu(ctx), 0)
        self.assertIn("== เครื่องมือ ==", self.io.text)

    def test_menu_survives_cancel_inside_an_action(self):
        ctx = self.ctx(answers=[commands.MENU_KEYS["tool"]])          # ถามชื่อ tool แต่คำตอบหมด = กด Ctrl+C
        self.assertEqual(menu.run_menu(ctx), 0)
        self.assertIn("ยกเลิกรายการนี้", self.io.text)

    def test_menu_can_create_a_tool(self):
        ctx = self.ctx(answers=[commands.MENU_KEYS["tool"], "check_stock", "", "0"])
        self.assertEqual(menu.run_menu(ctx), 0)
        self.assertTrue((self.root / "agent-kit" / "tools" / "check_stock.py").exists())

    def test_every_menu_key_is_wired(self):
        keys = {k for k, _ in menu.MENU}
        self.assertEqual(keys, set(commands.MENU_KEYS.values()) | {"0"})


class DefaultsDriftTest(unittest.TestCase):
    """ค่าเริ่มต้นใน settings.py ซ้ำกับ .env.example และ rag-pipeline/config.py ต้องไม่ลอยห่างกัน"""

    def test_defaults_match_env_example(self):
        example = envfile.read(ROOT / ".env.example")
        checked = 0
        for s in settings.SETTINGS:
            if s.kind != "secret" and example.get(s.key):
                self.assertEqual(example[s.key], s.default, s.key)
                checked += 1
        self.assertGreater(checked, 8)

    @unittest.skipUnless(importlib.util.find_spec("dotenv"), "ต้องมี python-dotenv")
    def test_defaults_match_rag_config(self):
        # คัดลอก config.py ไปโฟลเดอร์ชั่วคราว เพื่อไม่ให้ load_dotenv ไปอ่าน .env จริงของผู้ใช้
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ):
            for s in settings.SETTINGS:
                os.environ.pop(s.key, None)
            shutil.copy(ROOT / "rag-pipeline" / "config.py", Path(tmp) / "config.py")
            spec = importlib.util.spec_from_file_location("rag_config_for_drift_test", Path(tmp) / "config.py")
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
        pairs = {"RAG_TOP_K": "TOP_K", "RAG_CHUNK_SIZE": "CHUNK_SIZE", "RAG_CHUNK_OVERLAP": "CHUNK_OVERLAP",
                 "RAG_EMBED_MODEL": "EMBED_MODEL", "RAG_USE_RERANK": "USE_RERANK", "RAG_MAX_TOKENS": "MAX_TOKENS",
                 "LLM_PROVIDER": "LLM_PROVIDER", "CLAUDE_MODEL": "CLAUDE_MODEL", "OLLAMA_MODEL": "OLLAMA_MODEL",
                 "OLLAMA_URL": "OLLAMA_URL"}
        for key, attr in pairs.items():
            with self.subTest(key=key):
                self.assertEqual(str(getattr(config, attr)).lower(), settings.BY_KEY[key].default.lower())


class CommandLineTest(unittest.TestCase):
    def test_parser_shapes(self):
        parser = hope.build_parser()
        args = parser.parse_args(["ask", "ลาพักร้อน", "กี่วัน", "--top-k", "3"])
        self.assertEqual((args.question, args.top_k), (["ลาพักร้อน", "กี่วัน"], 3))
        args = parser.parse_args(["config", "set", "RAG_TOP_K", "5"])
        self.assertEqual((args.config_command, args.key, args.value), ("set", "RAG_TOP_K", "5"))
        self.assertIsNone(parser.parse_args(["config"]).config_command)
        self.assertEqual(parser.parse_args(["setup", "--profile", "rag", "-y"]).yes, True)
        self.assertIsNone(parser.parse_args([]).command)

    def test_no_command_without_a_terminal_prints_help(self):
        buffer = io.StringIO()
        with mock.patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stdout(buffer):
            self.assertEqual(hope.main([]), 0)
        self.assertIn("setup", buffer.getvalue())

    def test_setup_dry_run_through_the_real_entry_point(self):
        with mock.patch("builtins.print") as printed:
            self.assertEqual(hope.main(["setup", "--profile", "agent", "--yes", "--dry-run"]), 0)
        self.assertIn("คำสั่งติดตั้ง", " ".join(str(c.args[0]) for c in printed.call_args_list if c.args))


class LinkAnchorTest(unittest.TestCase):
    def test_slug_matches_github_rules(self):
        self.assertEqual(hope.github_slug("Check and test"), "check-and-test")
        self.assertEqual(hope.github_slug("เริ่มกับเอกสารของคุณ"), "เริ่มกับเอกสารของคุณ")
        self.assertEqual(hope.github_slug("ตรวจและทดสอบ (เร็ว)!"), "ตรวจและทดสอบ-เร็ว")
        self.assertEqual(hope.github_slug("ลิงก์ [คู่มือ](x.md) `code`"), "ลิงก์-คู่มือ-code")

    def test_anchors_handle_duplicates_and_code_fences(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "a.md"
            md.write_text("# Name\n## Name\n```\n# not a heading\n```\n### อื่น ๆ\n", encoding="utf-8")
            self.assertEqual(hope.anchors_of(md), {"name", "name-1", "อื่น-ๆ"})

    def test_repository_has_no_broken_links_or_anchors(self):
        checked, bad = hope.broken_links()
        self.assertEqual(bad, [])
        self.assertGreater(checked, 30)


class LauncherTest(unittest.TestCase):
    def test_windows_launcher_is_ascii_with_crlf(self):
        data = (ROOT / "start.cmd").read_bytes()
        self.assertTrue(all(b < 128 for b in data), "start.cmd ต้องเป็น ASCII ล้วน ไม่งั้น cmd.exe อ่านเพี้ยน")
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), "start.cmd ต้องใช้ CRLF ทุกบรรทัด")
        self.assertIn(b"hope.py", data)

    def test_unix_launcher_uses_lf_and_a_shebang(self):
        data = (ROOT / "start.sh").read_bytes()
        self.assertTrue(data.startswith(b"#!/bin/sh"))
        self.assertNotIn(b"\r", data)
        self.assertIn(b"hope.py", data)


if __name__ == "__main__":
    unittest.main()
