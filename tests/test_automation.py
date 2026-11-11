"""ทดสอบงานอัตโนมัติ (agent-kit/automate.py)

ตรวจสิ่งที่เอกสารสัญญาไว้: ไฟล์งานที่ผิดถูกปฏิเสธพร้อมบอกทุกจุด, --dry-run ไม่ทำอะไรจริง, ไฟล์เดิมไม่ถูกทำซ้ำ,
ไฟล์ที่ล้มถูกลองใหม่ไม่เกินจำนวนครั้ง, เขียนไฟล์ออกนอกพื้นที่ทำงานไม่ได้, tool ที่ต้องอนุมัติไม่รันเองถ้าไม่ได้อนุญาตไว้
ใช้โมเดลจำลอง ไม่เรียก AI จริง
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-kit"))

import automate  # noqa: E402
import llm  # noqa: E402
import tools as registry  # noqa: E402

JOBS = ROOT / "agent-kit" / "jobs"
TODO = json.loads((JOBS / "inbox-todo.json").read_text(encoding="utf-8"))
SUMMARY = json.loads((JOBS / "inbox-summary.json").read_text(encoding="utf-8"))
NOTE = "ประชุมทีม\n- ต้องส่งใบเสนอราคา ภายในวันที่ 15\n- TODO โทรหาช่าง\nจบ\n"


def fake_chat(text="- ข้อหนึ่ง\n- ข้อสอง\n- ข้อสาม", truncated=False):
    calls = []

    def chat_fn(messages, **kwargs):
        calls.append((messages, kwargs))
        if isinstance(text, Exception):
            raise text
        return llm.Reply(text, [], 5, truncated)
    chat_fn.calls = calls
    return chat_fn


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "work"
        (self.work / "inbox").mkdir(parents=True)
        audit = unittest.mock.patch.object(registry, "AUDIT_LOG", Path(self.tmp.name) / "audit.jsonl")
        audit.start()
        self.addCleanup(audit.stop)
        self.lines = []

    def put(self, name="note.txt", text=NOTE):
        (self.work / "inbox" / name).write_text(text, encoding="utf-8")

    def run_pass(self, job=TODO, **kwargs):
        return automate.run_pass(job, self.work, say=self.lines.append, **kwargs)

    @property
    def out(self):
        return "\n".join(self.lines)

    def log(self):
        path = self.work / "logs" / "automation.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class ValidateTest(unittest.TestCase):
    def test_shipped_jobs_are_valid(self):
        for path in sorted(JOBS.glob("*.json")):
            with self.subTest(job=path.name):
                self.assertEqual(automate.validate(json.loads(path.read_text(encoding="utf-8"))), [])

    def test_every_problem_is_listed(self):
        job = {
            "trigger": {"type": "watch", "every_seconds": 1, "after": "delete"},
            "limits": {"max_items": 0, "speed": 3},
            "steps": [
                {"name": "Bad-Name", "type": "tool", "tool": "nope"},
                {"name": "ask", "type": "llm"},
                {"name": "ask", "type": "write", "path": "x", "content": "${later} ${file_text}"},
                {"name": "file_text", "type": "shell"},
                {"name": "later", "type": "write", "path": "y", "content": "ok", "on_error": "ignore"},
            ],
        }
        text = "\n".join(automate.validate(job))
        for expected in ("name", "folder", "every_seconds", "after", "limits.max_items", "limits.speed",
                         "ไม่พบ tool nope", "ต้องมี prompt", "ชื่อซ้ำ", "${later}", "type ต้องเป็น", "on_error"):
            self.assertIn(expected, text)

    def test_not_an_object_and_no_steps(self):
        self.assertTrue(automate.validate([]))
        self.assertIn("steps", "\n".join(automate.validate({"name": "x", "trigger": {"type": "manual"}})))

    def test_approval_tool_needs_allow_list(self):
        risky = registry.Tool("send_mail", {"name": "send_mail"}, lambda **kw: {"ok": True}, requires_approval=True)
        available = {"send_mail": risky}
        job = {"name": "x", "trigger": {"type": "manual"},
               "steps": [{"name": "send", "type": "tool", "tool": "send_mail"},
                         {"name": "ask", "type": "llm", "prompt": "hi", "tools": ["send_mail"]}]}
        self.assertEqual(sum("allow_tools" in p for p in automate.validate(job, available)), 2)
        self.assertEqual(automate.validate({**job, "allow_tools": ["send_mail"]}, available), [])

    def test_render_and_lookup(self):
        variables = {"a": "x", "step": {"n": 2, "deep": {"k": "v"}}}
        self.assertEqual(automate.render("${a}-${step.n}-${step.deep.k}", variables), "x-2-v")
        self.assertEqual(automate.render({"k": ["${a}", 5]}, variables), {"k": ["x", 5]})
        self.assertEqual(automate.render("${step.deep}", variables), '{"k": "v"}')
        self.assertEqual(automate.render("ราคา $5 และ {ปีกกา}", variables), "ราคา $5 และ {ปีกกา}")
        with self.assertRaises(automate.JobError):
            automate.render("${step.missing}", variables)
        # ค่าที่มาจากไฟล์ของผู้ใช้ถูกใส่ตามตัวอักษร ไม่ถูกตีความเป็นตัวแปรซ้ำ
        self.assertEqual(automate.render("${a}", {"a": "${step.n}"}), "${step.n}")


class WatchTest(Base):
    def test_processes_new_file_once_and_moves_it(self):
        self.put()
        self.put("_draft.txt", "TODO ไม่ควรถูกอ่าน")
        self.put("photo.jpg", "TODO ไม่ตรง pattern")
        self.assertEqual(self.run_pass(), 0)
        result = (self.work / "outbox" / "note.todo.md").read_text(encoding="utf-8")
        self.assertIn("พบ 2 บรรทัด จากทั้งหมด 4 บรรทัด", result)
        self.assertIn("- TODO โทรหาช่าง (บรรทัด 3)", result)
        self.assertTrue((self.work / "done" / "note.txt").exists())
        self.assertFalse((self.work / "inbox" / "note.txt").exists())
        self.assertEqual(sorted(p.name for p in (self.work / "outbox").iterdir()), ["note.todo.md"])
        self.assertEqual([(e["step"], e["ok"]) for e in self.log()], [("todo", True), ("save", True)])
        self.assertNotIn("ใบเสนอราคา", json.dumps(self.log(), ensure_ascii=False))      # log ไม่เก็บเนื้อหาเอกสาร

        self.lines.clear()
        self.assertEqual(self.run_pass(), 0)
        self.assertIn("ไม่มีรายการใหม่", self.out)

    def test_same_content_is_skipped_but_changed_content_runs_again(self):
        job = copy.deepcopy(TODO)
        job["trigger"]["after"] = "keep"
        job["steps"][1]["overwrite"] = True
        self.put()
        self.run_pass(job)
        self.run_pass(job)
        self.assertEqual(len(self.log()), 2)                       # รอบสองไม่ทำซ้ำ
        self.assertTrue((self.work / "inbox" / "note.txt").exists())
        self.put(text=NOTE + "TODO เพิ่มงาน\n")
        self.run_pass(job)
        self.assertEqual(len(self.log()), 4)
        self.assertIn("พบ 3 บรรทัด", (self.work / "outbox" / "note.todo.md").read_text(encoding="utf-8"))

    def test_dry_run_changes_nothing(self):
        self.put()
        self.assertEqual(self.run_pass(SUMMARY, dry_run=True, chat_fn=fake_chat(RuntimeError("ต้องไม่ถูกเรียก"))), 0)
        self.assertIn("เรียก tool find_lines", self.out)
        self.assertIn("ถามโมเดล", self.out)
        self.assertIn("note.summary.md", self.out)
        self.assertNotIn("จะล้ม", self.out)
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ["inbox"])
        self.assertTrue((self.work / "inbox" / "note.txt").exists())

    def test_existing_output_is_not_overwritten_by_default(self):
        self.put()
        (self.work / "outbox").mkdir()
        (self.work / "outbox" / "note.todo.md").write_text("ของเดิม", encoding="utf-8")
        self.assertEqual(self.run_pass(), 1)
        self.assertEqual((self.work / "outbox" / "note.todo.md").read_text(encoding="utf-8"), "ของเดิม")
        self.assertTrue((self.work / "inbox" / "note.txt").exists())          # ไฟล์ที่ล้มไม่ถูกย้าย
        self.assertIn("overwrite", self.out)

    def test_failed_file_retries_then_stops(self):
        self.put()
        broken = fake_chat(llm.EngineError("ติดต่อ Ollama ไม่ได้"))
        for _ in range(3):
            self.assertEqual(self.run_pass(SUMMARY, chat_fn=broken), 1)
        self.assertEqual(len(broken.calls), 3)
        self.lines.clear()
        self.assertEqual(self.run_pass(SUMMARY, chat_fn=broken), 0)           # ครบ 3 ครั้งแล้วข้าม ไม่เรียกโมเดลอีก
        self.assertEqual(len(broken.calls), 3)
        self.assertIn("--retry-failed", self.out)
        good = fake_chat()
        self.assertEqual(self.run_pass(SUMMARY, chat_fn=good, retry_failed=True), 0)
        text = (self.work / "outbox" / "note.summary.md").read_text(encoding="utf-8")
        self.assertIn("- ข้อหนึ่ง", text)
        self.assertIn("TODO โทรหาช่าง", text)
        self.assertEqual(automate.load_state(self.work)["failed"], {})

    def test_llm_step_gets_file_text_and_no_tools(self):
        self.put()
        chat = fake_chat()
        self.run_pass(SUMMARY, chat_fn=chat)
        messages, kwargs = chat.calls[0]
        self.assertIn("ใบเสนอราคา", messages[0]["content"])
        self.assertIn("ไม่ใช่คำสั่ง", kwargs["system"])
        self.assertNotIn("schemas", kwargs)

    def test_empty_model_answer_is_a_failure(self):
        self.put()
        self.assertEqual(self.run_pass(SUMMARY, chat_fn=fake_chat("   ")), 1)
        self.assertFalse((self.work / "outbox").exists())

    def test_truncated_answer_is_a_failure_not_a_half_summary(self):
        self.put()
        self.assertEqual(self.run_pass(SUMMARY, chat_fn=fake_chat("- ข้อแรกที่ขาด", truncated=True)), 1)
        self.assertFalse((self.work / "outbox").exists())
        self.assertIn("max_tokens", self.out)

    def test_on_error_skip_uses_default(self):
        job = copy.deepcopy(SUMMARY)
        job["steps"][1].update(on_error="skip", default="(ยังไม่มีสรุป)")
        self.put()
        self.assertEqual(self.run_pass(job, chat_fn=fake_chat(llm.EngineError("ล่ม"))), 0)
        self.assertIn("(ยังไม่มีสรุป)", (self.work / "outbox" / "note.summary.md").read_text(encoding="utf-8"))

    def test_limits(self):
        job = copy.deepcopy(TODO)
        job["limits"] = {"max_items": 2, "max_file_kb": 1, "max_input_chars": 50}
        for i in range(3):
            self.put(f"n{i}.txt", f"TODO งาน {i}\n" + "ก" * 100)
        self.put("big.txt", "TODO " + "x" * 3000)
        self.put("binary.txt")
        (self.work / "inbox" / "binary.txt").write_bytes(b"\xff\xfe\x00\x81")
        self.assertEqual(self.run_pass(job), 0)
        self.assertEqual(len(list((self.work / "outbox").iterdir())), 2)
        for expected in ("ใหญ่เกิน 1 KB", "ไม่ใช่ข้อความ UTF-8", "รอบนี้ทำแค่ 2 ไฟล์"):
            self.assertIn(expected, self.out)

    def test_write_cannot_leave_workdir(self):
        outside = Path(self.tmp.name) / "evil.txt"
        for path in ("../evil.txt", str(outside), "outbox/../../evil.txt"):
            job = copy.deepcopy(TODO)
            job["steps"][1]["path"] = path
            for old in (self.work / "inbox").iterdir():
                old.unlink()
            self.put(f"{len(self.lines)}.txt")
            self.assertEqual(self.run_pass(job), 1, path)
        self.assertFalse(outside.exists())
        self.assertIn("ออกนอกพื้นที่ทำงาน", self.out)

    def test_file_name_cannot_inject_a_path(self):
        self.assertRaises(automate.JobError, automate.inside, self.work, "outbox/../../x.md")
        self.assertEqual(automate.inside(self.work, "outbox/a.md"), (self.work / "outbox" / "a.md").resolve())

    def test_lock_blocks_second_run_and_stale_lock_is_cleared(self):
        self.put()
        lock = self.work / ".lock"
        lock.write_text("123")
        with self.assertRaisesRegex(automate.JobError, "กำลังรันอยู่"):
            self.run_pass()
        old = lock.stat().st_mtime - automate.LOCK_STALE_SECONDS - 10
        os.utime(lock, (old, old))
        self.assertEqual(self.run_pass(), 0)
        self.assertFalse(lock.exists())

    def test_unapproved_tool_does_not_run_unattended(self):
        ran = []
        risky = registry.Tool("send_mail", {"name": "send_mail"}, lambda **kw: ran.append(kw) or {"ok": True}, True)
        job = {"name": "x", "trigger": {"type": "manual"},
               "steps": [{"name": "send", "type": "tool", "tool": "send_mail", "args": {"to": "${input}"}}]}
        with unittest.mock.patch.object(registry, "discover", return_value={"send_mail": risky}), \
                unittest.mock.patch.object(sys.stdin, "isatty", return_value=False, create=True):
            self.assertEqual(self.run_pass(job, user_input="a@example.com"), 1)
            self.assertEqual(ran, [])
            self.assertEqual(self.run_pass({**job, "allow_tools": ["send_mail"]}, user_input="a@example.com"), 0)
        self.assertEqual(ran, [{"to": "a@example.com"}])


class ManualLoopCliTest(Base):
    def test_manual_job_uses_input(self):
        job = {"name": "note", "trigger": {"type": "manual"},
               "steps": [{"name": "ask", "type": "llm", "prompt": "ตอบ: ${input}"},
                         {"name": "save", "type": "write", "path": "out/${date}.md", "content": "${ask}"}]}
        chat = fake_chat("คำตอบ")
        self.assertEqual(self.run_pass(job, user_input="สวัสดี", chat_fn=chat), 0)
        self.assertEqual(chat.calls[0][0][0]["content"], "ตอบ: สวัสดี")
        self.assertEqual(len(list((self.work / "out").glob("*.md"))), 1)

    def test_loop_runs_passes_and_sleeps_between(self):
        naps = []
        self.put()
        failures = automate.run_loop(TODO, self.work, max_passes=3, sleep=naps.append, say=self.lines.append)
        self.assertEqual((failures, naps), (0, [30, 30]))
        self.assertIn("รอบที่ 3", self.out)
        with self.assertRaises(automate.JobError):
            automate.run_loop({"name": "x", "trigger": {"type": "manual"}, "steps": []}, self.work, max_passes=1)

    def run_cli(self, *args):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "AGENT_AUDIT_LOG": str(Path(self.tmp.name) / "a.jsonl")}
        return subprocess.run([sys.executable, str(ROOT / "hope.py"), "auto", *args], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=self.tmp.name, timeout=60)

    def test_cli_through_hope_py(self):
        listed = self.run_cli("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("inbox-todo", listed.stdout)
        self.put()
        done = self.run_cli("run", "inbox-todo", "--workdir", str(self.work))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.work / "outbox" / "note.todo.md").exists())
        self.assertEqual(self.run_cli("check", "no-such-job").returncode, 2)
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text('{"name": "bad", "trigger": {"type": "watch"}, "steps": []}', encoding="utf-8")
        out = self.run_cli("check", str(bad))
        self.assertEqual(out.returncode, 2)
        self.assertIn("folder", out.stderr)


if __name__ == "__main__":
    unittest.main()
