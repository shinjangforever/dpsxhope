"""ทดสอบตัวอย่างของเครื่องมือในแผนที่ stack และบทเรียนเป็นขั้น

ครอบ: รายงานจาก log ด้วย SQLite, คำสั่งตั้งเวลา, ช่องรับไฟล์ทาง HTTP, MCP server, คำสั่ง audit, ตัวอย่าง C++ (ถ้ามีตัวคอมไพล์),
หน้าเว็บตัวอย่าง (ตรวจโครงและกติกาความปลอดภัยในไฟล์) และรันทุกคำสั่งในบทเรียนที่ไม่ต้องใช้โมเดล
ไม่ครอบ: การตั้งเวลาจริงในระบบปฏิบัติการ, n8n จริง, แอป MCP จริง, หน้าเว็บในเบราว์เซอร์ (ทดสอบด้วยมือ)
"""
import io
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent-kit"))
sys.path.insert(0, str(ROOT / "fields" / "robotics"))

import autotools  # noqa: E402
import mcp_server  # noqa: E402
import tools as registry  # noqa: E402
import hope  # noqa: E402
from hopekit import audit, stackmap  # noqa: E402
from robokit import stopping  # noqa: E402

TOKEN = "test-token-0123456789"


def log_line(item, step, ok, ms=10, kind="tool", error=None):
    entry = {"time": "2026-11-12T10:00:00+0700", "job": "j", "item": item, "step": step, "type": kind, "ok": ok, "ms": ms}
    if error:
        entry["error"] = error
    return json.dumps(entry, ensure_ascii=False)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        audit_log = unittest.mock.patch.object(registry, "AUDIT_LOG", self.dir / "audit.jsonl")
        audit_log.start()
        self.addCleanup(audit_log.stop)


class ReportTest(Base):
    def write_log(self):
        (self.dir / "logs").mkdir()
        lines = [
            log_line("a.txt", "todo", True, 10), log_line("a.txt", "save", True, 30, "write"),
            log_line("b.txt", "todo", True, 20), log_line("b.txt", "save", False, 5, "write", "มีไฟล์อยู่แล้ว"),
            log_line("c.txt", "todo", True, 30), log_line("c.txt", "save", False, 5, "write", "มีไฟล์อยู่แล้ว"),
            "not json", "{}",
            log_line("c.txt", "todo", True, 30), log_line("c.txt", "save", True, 40, "write"),   # c ลองใหม่แล้วผ่าน
        ]
        (self.dir / "logs" / "automation.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_summary_counts_latest_result_per_item(self):
        self.write_log()
        con = autotools.load_log(self.dir / "logs" / "automation.jsonl")
        data = autotools.summarize(con)
        con.close()
        self.assertEqual((data["items"], data["succeeded"], data["failed"]), (3, 2, 1))
        self.assertEqual(data["machine_ms"], 170)
        steps = {s["step"]: s for s in data["steps"]}
        self.assertEqual((steps["save"]["runs"], steps["save"]["failures"]), (4, 2))
        self.assertEqual(steps["todo"]["avg_ms"], 22)
        self.assertEqual(data["errors"], [{"error": "มีไฟล์อยู่แล้ว", "count": 2}])

    def test_report_text_json_and_database(self):
        self.write_log()
        lines = []
        db = self.dir / "log.db"
        self.assertEqual(autotools.report(self.dir, lines.append, minutes_by_hand=3, db_path=db), 0)
        text = "\n".join(lines)
        self.assertIn("สำเร็จ 2  ล้ม 1", text)
        self.assertIn("ใช้ราว 6 นาที", text)
        self.assertIn("ยังไม่รวมเวลาที่คุณใช้ตรวจผล", text)
        con = sqlite3.connect(db)                      # ไฟล์ที่ได้เปิดถามด้วย SQL ธรรมดาได้
        self.assertEqual(con.execute("SELECT COUNT(*) FROM steps WHERE ok = 0").fetchone()[0], 2)
        con.close()
        lines.clear()
        autotools.report(self.dir, lines.append, as_json=True)
        self.assertEqual(json.loads(lines[0])["items"], 3)

    def test_missing_log_is_explained(self):
        with self.assertRaisesRegex(autotools.ToolError, "ยังไม่มี log"):
            autotools.report(self.dir)


class ScheduleTest(unittest.TestCase):
    HOPE = Path("C:/x y/hope.py")

    def test_windows_command(self):
        cmd = autotools.schedule_commands("inbox-todo", self.HOPE, "C:/py/python.exe", 15, windows=True)
        self.assertIn('/TN "dpsxhope-inbox-todo" /SC MINUTE /MO 15', cmd["create"])
        self.assertIn('\\"C:/py/python.exe\\"', cmd["create"])            # ที่อยู่ที่มีเว้นวรรคถูกครอบด้วยเครื่องหมายคำพูด
        self.assertIn("auto run inbox-todo", cmd["create"])
        self.assertIn("/Delete", cmd["remove"])
        hourly = autotools.schedule_commands("j", self.HOPE, "py", 120, windows=True)
        self.assertIn("/SC HOURLY /MO 2", hourly["create"])

    def test_cron_command(self):
        cmd = autotools.schedule_commands("inbox-todo", Path("/home/u/dpsxhope/hope.py"), "/usr/bin/python3", 15, windows=False)
        self.assertIn("*/15 * * * * cd '/home/u/dpsxhope'", cmd["create"].replace("\\", "/"))
        self.assertIn("hope.py auto run inbox-todo", cmd["create"])
        self.assertIn("0 */3 * * *", autotools.schedule_commands("j", Path("/h/hope.py"), "py", 180, windows=False)["create"])

    def test_bad_input_is_refused(self):
        for job, minutes in (("a b", 15), ("x; rm -rf /", 15), ('x" & calc', 15), ("ok", 0), ("ok", 90), ("ok", 1440)):
            with self.subTest(job=job, minutes=minutes), self.assertRaises(autotools.ToolError):
                autotools.schedule_commands(job, self.HOPE, "py", minutes, windows=True)

    def test_show_says_it_does_not_install(self):
        lines = []
        autotools.show_schedule("inbox-todo", self.HOPE, 15, lines.append, windows=True)
        text = "\n".join(lines)
        self.assertIn("ไม่ได้ตั้งเวลาให้", text)
        self.assertIn("ยังไม่ได้ทดสอบโดยการตั้งเวลาจริง", text)


class InboxServerTest(Base):
    def setUp(self):
        super().setUp()
        self.inbox = self.dir / "inbox"
        self.server = autotools.make_server(self.inbox, ["*.txt"], TOKEN, 200, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def post(self, body, token=TOKEN, path="/inbox"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + path, data=data, headers=headers)) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def test_accepts_a_valid_file_once(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")          # รับเฉพาะจากเครื่องนี้
        self.assertEqual(self.post({"name": "บันทึก 1.txt", "text": "TODO ทดสอบ"}), (201, {"saved": "บันทึก 1.txt"}))
        self.assertEqual((self.inbox / "บันทึก 1.txt").read_text(encoding="utf-8"), "TODO ทดสอบ")
        self.assertEqual(self.post({"name": "บันทึก 1.txt", "text": "ทับ"})[0], 409)
        self.assertEqual((self.inbox / "บันทึก 1.txt").read_text(encoding="utf-8"), "TODO ทดสอบ")
        with urllib.request.urlopen(self.url + "/health") as resp:
            self.assertEqual(json.load(resp), {"status": "ok"})

    def test_refuses_bad_token_names_and_sizes(self):
        self.assertEqual(self.post({"name": "a.txt", "text": "x"}, token=None)[0], 401)
        self.assertEqual(self.post({"name": "a.txt", "text": "x"}, token="wrong-token-0123456789")[0], 401)
        for name in ("../a.txt", "sub/a.txt", "..\\a.txt", ".hidden.txt", "_skip.txt", "a.exe", "a.txt\n", "", None, 5,
                     "C:\\a.txt", "a" * 120 + ".txt"):
            with self.subTest(name=name):
                self.assertEqual(self.post({"name": name, "text": "x"})[0], 400)
        self.assertEqual(self.post({"name": "a.txt", "text": ""})[0], 400)
        self.assertEqual(self.post({"name": "a.txt", "text": "ก" * 100})[0], 413)       # 300 ไบต์ เกิน 200
        self.assertEqual(self.post(b"not json")[0], 400)
        self.assertEqual(self.post(["list"])[0], 400)
        self.assertEqual(self.post({"name": "a.txt", "text": "x"}, path="/other")[0], 404)
        self.assertEqual(list(self.inbox.iterdir()), [])
        self.assertFalse((self.dir / "a.txt").exists())

    def test_short_token_refuses_to_start(self):
        with self.assertRaisesRegex(autotools.ToolError, "AUTO_WEBHOOK_TOKEN"):
            autotools.make_server(self.inbox, ["*.txt"], "short", 200, 0)


class McpServerTest(Base):
    def server(self, names=("calculate",)):
        return mcp_server.Server(mcp_server.exposed(list(names)))

    def call(self, server, method, params=None, request_id=1):
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        return server.handle(message)

    def test_initialize_negotiates_version(self):
        s = self.server()
        result = self.call(s, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")              # รองรับ จึงตอบรุ่นเดิม
        self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(result["serverInfo"]["name"], "dpsxhope-agent-kit")
        newer = self.call(s, "initialize", {"protocolVersion": "2026-07-28"})["result"]
        self.assertEqual(newer["protocolVersion"], "2025-11-25")               # ไม่รองรับ จึงตอบรุ่นล่าสุดที่รองรับ

    def test_list_and_call(self):
        s = self.server()
        listed = self.call(s, "tools/list")["result"]["tools"]
        self.assertEqual([t["name"] for t in listed], ["calculate"])
        self.assertEqual(set(listed[0]), {"name", "description", "inputSchema"})
        self.assertEqual(listed[0]["inputSchema"]["type"], "object")
        result = self.call(s, "tools/call", {"name": "calculate", "arguments": {"expression": "6*7"}})["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertEqual(json.loads(result["content"][0]["text"])["result"], 42)
        self.assertTrue((self.dir / "audit.jsonl").exists())                    # การเรียกผ่าน MCP ก็ลง audit log

    def test_tool_failure_is_a_result_but_unknown_tool_is_a_protocol_error(self):
        s = self.server()
        failed = self.call(s, "tools/call", {"name": "calculate", "arguments": {"expression": "import os"}})["result"]
        self.assertTrue(failed["isError"])
        unknown = self.call(s, "tools/call", {"name": "delete_all", "arguments": {}})
        self.assertEqual(unknown["error"]["code"], -32602)
        self.assertEqual(self.call(s, "tools/call", {"name": "calculate", "arguments": "6*7"})["error"]["code"], -32602)
        self.assertEqual(self.call(s, "server/discover")["error"]["code"], -32601)
        self.assertEqual(self.call(s, "ping")["result"], {})

    def test_notifications_get_no_reply_and_bad_messages_get_errors(self):
        s = self.server()
        self.assertIsNone(s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(s.handle({"id": 1, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(s.handle([1, 2])["error"]["code"], -32600)

    def test_approval_tools_are_never_exposed(self):
        risky = registry.Tool("pay", {"name": "pay", "input_schema": {"type": "object"}}, lambda: {"ok": True}, True)
        safe = registry.discover()["calculate"]
        with unittest.mock.patch.object(registry, "discover", return_value={"pay": risky, "calculate": safe}):
            self.assertEqual(list(mcp_server.exposed()), ["calculate"])
            self.assertEqual(list(mcp_server.exposed(["pay"])), [])

    def test_stdio_is_one_json_message_per_line(self):
        requests = [
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}',
            '{"jsonrpc":"2.0","method":"notifications/initialized"}',
            "", "this is not json",
            '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"find_lines","arguments":{"text":"a\\nTODO b","keywords":["todo"]}}}',
        ]
        out = io.StringIO()
        mcp_server.serve(self.server(("find_lines",)), io.StringIO("\n".join(requests) + "\n"), out)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 3)                                         # notification และบรรทัดว่างไม่มีคำตอบ
        replies = [json.loads(line) for line in lines]                          # ทุกบรรทัดเป็น JSON ที่สมบูรณ์
        self.assertEqual([r.get("id") for r in replies], [1, None, 2])
        self.assertEqual(replies[1]["error"]["code"], -32700)
        self.assertIn("TODO b", replies[2]["result"]["content"][0]["text"])

    def test_process_speaks_only_mcp_on_stdout(self):
        done = subprocess.run([sys.executable, str(ROOT / "agent-kit" / "mcp_server.py"), "--tools", "calculate"],
                              input='{"jsonrpc":"2.0","id":7,"method":"tools/list"}\n', capture_output=True, text=True,
                              encoding="utf-8", timeout=60,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8", "AGENT_AUDIT_LOG": str(self.dir / "a.jsonl")})
        self.assertEqual(done.returncode, 0, done.stderr)                       # ปิด stdin แล้วจบเอง
        self.assertEqual(json.loads(done.stdout)["id"], 7)
        self.assertIn("MCP server", done.stderr)


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ai-api").mkdir()
        (self.root / "ai-api" / "package-lock.json").write_text("{}", encoding="utf-8")

    def test_npm_states(self):
        has_npm = lambda _name: "npm"
        self.assertEqual(audit.npm_audit(self.root, which=lambda _n: None)[0], audit.SKIPPED)
        self.assertEqual(audit.npm_audit(self.root, lambda a, c: (0, "found 0 vulnerabilities"), has_npm)[0], audit.CLEAN)
        self.assertEqual(audit.npm_audit(self.root, lambda a, c: (1, "3 high severity vulnerabilities"), has_npm)[0], audit.FOUND)
        self.assertEqual(audit.npm_audit(self.root, lambda a, c: (1, "network error ENOTFOUND"), has_npm)[0], audit.FAILED)
        calls = []
        audit.npm_audit(self.root, lambda a, c: calls.append((a, c)) or (0, ""), has_npm)
        self.assertEqual(calls[0][0][1:], ["audit", "--omit=dev"])
        self.assertEqual(calls[0][1], self.root / "ai-api")

    def test_pip_states(self):
        have = lambda python, names: {"pip_audit": True}
        state, detail = audit.pip_audit(self.root, modules=lambda python, names: {"pip_audit": False})
        self.assertEqual(state, audit.SKIPPED)
        self.assertIn("pip install pip-audit", detail)
        self.assertEqual(audit.pip_audit(self.root, lambda a, c: (0, "No known vulnerabilities found"), have)[0], audit.CLEAN)
        self.assertEqual(audit.pip_audit(self.root, lambda a, c: (1, "Found 2 known vulnerabilities in 1 package"), have)[0],
                         audit.FOUND)
        self.assertEqual(audit.pip_audit(self.root, lambda a, c: (2, "connection refused"), have)[0], audit.FAILED)

    def test_report_exit_codes(self):
        lines = []
        clean = {"a": lambda r: (audit.CLEAN, "ok"), "b": lambda r: (audit.SKIPPED, "ไม่มีเครื่องมือ")}
        self.assertEqual(audit.report(self.root, lines.append, clean), 0)
        self.assertEqual(audit.report(self.root, lines.append, {"a": lambda r: (audit.FOUND, "x\nvulnerability")}), 1)
        self.assertEqual(audit.report(self.root, lines.append, {"a": lambda r: (audit.FAILED, "net")}), 1)
        lines.clear()
        self.assertEqual(audit.report(self.root, lines.append, {"a": lambda r: (audit.SKIPPED, "-")}), 0)
        self.assertIn("ไม่ได้ตรวจอะไรเลย", "\n".join(lines))
        self.assertIn("ไม่ได้ตรวจโค้ดของคุณเอง", "\n".join(lines))


COMPILER = next((c for c in ("g++", "clang++", "c++") if shutil.which(c)), None)


class CppExampleTest(Base):
    SOURCE = ROOT / "languages" / "cpp" / "stop_distance.cpp"

    def test_source_states_the_same_formula_as_robokit(self):
        text = self.SOURCE.read_text(encoding="utf-8")
        self.assertIn("speed * react", text)
        self.assertIn("speed * speed / (2.0 * decel)", text)
        self.assertIn("std::isfinite", text)

    @unittest.skipUnless(COMPILER, "ไม่มีตัวคอมไพล์ C++ (g++ หรือ clang++) ในเครื่องนี้")
    def test_compiled_program_matches_robokit(self):
        exe = self.dir / ("stop_distance.exe" if os.name == "nt" else "stop_distance")
        build = subprocess.run([COMPILER, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(exe), str(self.SOURCE)],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(build.returncode, 0, build.stderr)
        for speed, react, decel, available in ((0.5, 0.2, 2.0, 0.4), (1.0, 0.2, 2.0, 0.4), (0.0, 0.1, 1.0, 0.0), (3.2, 0.05, 6.5, 2.0)):
            with self.subTest(speed=speed):
                done = subprocess.run([str(exe), str(speed), str(react), str(decel), str(available)], capture_output=True)
                react_d, brake_d, total, required, fits = done.stdout.decode("utf-8").splitlines()[0].split()
                want = stopping.check(speed, react, decel, available)
                self.assertAlmostEqual(float(react_d), want.react_distance, places=5)
                self.assertAlmostEqual(float(brake_d), want.brake_distance, places=5)
                self.assertAlmostEqual(float(total), want.total, places=5)
                self.assertAlmostEqual(float(required), want.required, places=5)
                self.assertEqual(fits == "1", want.ok)
                self.assertEqual(done.returncode, 0 if want.ok else 1)
        for bad in (["nan", "0.2", "2", "1"], ["0.5", "0.2", "0", "1"], ["-1", "0.2", "2", "1"], ["abc", "0.2", "2", "1"],
                    ["0.5", "0.2", "2", "1", "0.5"], ["inf", "0.2", "2", "1"], ["0.5"]):
            with self.subTest(bad=bad):
                self.assertEqual(subprocess.run([str(exe), *bad], capture_output=True).returncode, 2)


class WebExampleTest(unittest.TestCase):
    PAGE = (ROOT / "stack" / "examples" / "web" / "index.html").read_text(encoding="utf-8")

    def test_page_is_self_contained(self):
        self.assertIn('<html lang="th">', self.PAGE)
        self.assertIn('name="viewport"', self.PAGE)
        for external in ("<script src", "<link rel=\"stylesheet\"", "https://", "@import"):
            self.assertNotIn(external, self.PAGE)                               # ไม่โหลดอะไรจากภายนอก

    def test_page_follows_its_own_safety_notes(self):
        self.assertNotIn("innerHTML", self.PAGE)                                # คำตอบของโมเดลไม่ถูกรันเป็น HTML
        self.assertIn("textContent", self.PAGE)
        self.assertIn('type="password"', self.PAGE)
        for storage in ("localStorage", "sessionStorage", "document.cookie"):
            self.assertNotIn(storage, self.PAGE)                                # รหัสไม่ถูกบันทึก
        self.assertIn("/api/chat", self.PAGE)
        self.assertIn("Authorization", self.PAGE)

    def test_every_input_has_a_label(self):
        for field in ("api", "key", "message"):
            self.assertIn(f'<label for="{field}">', self.PAGE)
            self.assertIn(f'id="{field}"', self.PAGE)
        self.assertIn('aria-live="polite"', self.PAGE)
        self.assertIn("prefers-color-scheme: dark", self.PAGE)


class LessonsTest(Base):
    S = stackmap.load(ROOT)

    def test_lessons_are_complete_and_valid(self):
        self.assertEqual(stackmap.lesson_problems(self.S), [])
        self.assertEqual(len(self.S.lessons), len(self.S.tracks) * len(self.S.levels))

    def test_known_commands_match_hope_py(self):
        parser = hope.build_parser()
        choices = next(a.choices for a in parser._actions if getattr(a, "choices", None) and "status" in a.choices)
        self.assertEqual(stackmap.HOPE_COMMANDS, set(choices))

    def test_problems_are_caught(self):
        broken = stackmap.StackData(self.S.data, {"agent/1": {"steps": [{"do": "x", "run": "python hope.py nope"},
                                                                         {"auto": True}], "check": ""},
                                                  "ghost/9": {"steps": [], "check": "x"}})
        text = "\n".join(stackmap.lesson_problems(broken))
        for expected in ("agent/2: ยังไม่มี", "ghost/9: ไม่ตรง", "อย่างน้อย 3 ขั้น", "ต้องมี check", "ต้องมี do",
                         "auto ต้องมี run", "ไม่มีคำสั่ง hope.py nope"):
            self.assertIn(expected, text)

    def test_files_named_in_steps_exist(self):
        # ข้อความ "see" ของขั้นที่ไม่มีคำสั่ง มักชี้ไปยังไฟล์ ถ้าขึ้นต้นด้วยที่อยู่ไฟล์ ไฟล์นั้นต้องมีจริง
        for key, lesson in self.S.lessons.items():
            for step in lesson["steps"]:
                first = step.get("see", "").split(" ")[0]
                if "/" in first and not first.startswith("http") and "." in first.rsplit("/", 1)[-1]:
                    if first.startswith("agent-kit/logs/"):
                        continue                                                # ไฟล์ log เกิดตอนใช้งาน
                    with self.subTest(lesson=key, path=first):
                        self.assertTrue((ROOT / first).exists(), first)

    def test_every_offline_command_in_the_lessons_runs(self):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "AGENT_AUDIT_LOG": str(self.dir / "audit.jsonl")}
        for key in ("LLM_PROVIDER", "ANTHROPIC_API_KEY"):
            env.pop(key, None)
        seen = set()
        for key, lesson in self.S.lessons.items():
            for step in lesson["steps"]:
                if not step.get("auto") or step["run"] in seen:
                    continue
                seen.add(step["run"])
                args = shlex.split(step["run"])
                self.assertEqual(args[0], "python", step["run"])
                with self.subTest(lesson=key, run=step["run"]):
                    done = subprocess.run([sys.executable, *args[1:]], cwd=ROOT, env=env, capture_output=True, text=True,
                                          encoding="utf-8", errors="replace", timeout=180)
                    self.assertEqual(done.returncode, step.get("exit", 0), (done.stdout + done.stderr)[-600:])
        self.assertGreaterEqual(len(seen), 20)

    def test_lesson_numbers_match_the_tools(self):
        # ตัวเลขที่บทเรียนคณิตศาสตร์บอกให้คำนวณด้วยมือ ต้องตรงกับเครื่องมือ
        report = stopping.check(0.5, 0.2, 2.0, 0.4)
        self.assertEqual((report.react_distance, report.brake_distance, report.total), (0.1, 0.0625, 0.1625))
        self.assertEqual(stopping.check(1.0, 0.2, 2.0, 0.4).brake_distance, 0.25)
        self.assertEqual(round(28 / 30 * 100, 1), 93.3)

    def test_learn_view(self):
        lines = []
        self.assertEqual(stackmap.show_learn(self.S, lines.append, "security", 4), 0)
        text = "\n".join(lines)
        self.assertIn("THREAT-MODEL.md", text)
        self.assertIn("ผ่านเมื่อ", text)
        self.assertNotIn("ระดับ 3", text)


if __name__ == "__main__":
    unittest.main()
