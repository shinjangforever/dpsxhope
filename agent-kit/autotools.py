"""autotools.py — ส่วนเสริมของงานอัตโนมัติ: รายงานจาก log ด้วย SQLite, คำสั่งตั้งเวลา และช่องรับไฟล์ทาง HTTP

เรียกผ่าน automate.py: report, schedule, serve ใช้ไลบรารีมาตรฐานอย่างเดียว
"""
from __future__ import annotations

import fnmatch
import hmac
import json
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SAFE_NAME = re.compile(r"^[A-Za-z0-9ก-๙][A-Za-z0-9ก-๙ _.\-]{0,99}$")
TOKEN_ENV = "AUTO_WEBHOOK_TOKEN"
MIN_TOKEN_LENGTH = 16


class ToolError(Exception):
    pass


# ---------- รายงานจาก log ด้วย SQLite ----------

SCHEMA = """
CREATE TABLE steps (
    id INTEGER PRIMARY KEY,
    time TEXT NOT NULL, job TEXT NOT NULL, item TEXT NOT NULL,
    step TEXT NOT NULL, type TEXT NOT NULL, ok INTEGER NOT NULL, ms INTEGER NOT NULL, error TEXT
);
CREATE INDEX steps_item ON steps (item, id);
"""

# ผลล่าสุดของแต่ละไฟล์: แถวสุดท้ายที่บันทึกของไฟล์นั้นสำเร็จหรือล้ม
LAST_PER_ITEM = """
SELECT item, ok FROM steps s
WHERE id = (SELECT MAX(id) FROM steps WHERE item = s.item)
"""


def load_log(log_path: Path, db_path: Path | None = None) -> sqlite3.Connection:
    """อ่าน automation.jsonl ลงตาราง steps (ในหน่วยความจำ หรือไฟล์ .db ถ้าระบุ) บรรทัดที่เสียถูกข้าม"""
    if not log_path.is_file():
        raise ToolError(f"ยังไม่มี log ที่ {log_path} (รันงานอย่างน้อยหนึ่งรอบก่อน)")
    if db_path and db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path) if db_path else ":memory:")
    con.executescript(SCHEMA)
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            rows.append((e["time"], e["job"], e["item"], e["step"], e["type"], int(bool(e["ok"])), int(e["ms"]),
                         e.get("error")))
        except (ValueError, KeyError, TypeError):
            continue
    con.executemany("INSERT INTO steps (time, job, item, step, type, ok, ms, error) VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return con


def summarize(con: sqlite3.Connection) -> dict:
    items = con.execute(f"SELECT COUNT(*), COALESCE(SUM(ok), 0) FROM ({LAST_PER_ITEM})").fetchone()
    total_ms, first, last = con.execute("SELECT COALESCE(SUM(ms), 0), MIN(time), MAX(time) FROM steps").fetchone()
    steps = con.execute("""SELECT step, type, COUNT(*), SUM(1 - ok), CAST(AVG(ms) AS INTEGER), MAX(ms)
                           FROM steps GROUP BY step, type ORDER BY MIN(id)""").fetchall()
    errors = con.execute("""SELECT error, COUNT(*) FROM steps WHERE ok = 0 AND error IS NOT NULL
                            GROUP BY error ORDER BY COUNT(*) DESC, error LIMIT 5""").fetchall()
    return {"items": items[0], "succeeded": items[1], "failed": items[0] - items[1], "machine_ms": total_ms,
            "first": first, "last": last,
            "steps": [{"step": s, "type": t, "runs": n, "failures": f, "avg_ms": a, "max_ms": m}
                      for s, t, n, f, a, m in steps],
            "errors": [{"error": e, "count": n} for e, n in errors]}


def report(workdir: Path, say=print, minutes_by_hand: float | None = None, db_path: Path | None = None,
           as_json: bool = False) -> int:
    con = load_log(workdir / "logs" / "automation.jsonl", db_path)
    data = summarize(con)
    con.close()
    if minutes_by_hand is not None:
        data["by_hand_minutes"] = round(data["succeeded"] * minutes_by_hand, 1)
        data["machine_minutes"] = round(data["machine_ms"] / 60000, 1)
    if as_json:
        say(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if not data["items"]:
        say("log ยังไม่มีรายการ")
        return 0
    say(f"ช่วงเวลา {data['first']} ถึง {data['last']}")
    say(f"รายการทั้งหมด {data['items']}  สำเร็จ {data['succeeded']}  ล้ม {data['failed']} (นับจากผลล่าสุดของแต่ละรายการ)")
    say(f"เวลาที่เครื่องใช้รวม {data['machine_ms'] / 1000:.1f} วินาที\n")
    say(f"  {'ขั้น':<14}{'ชนิด':<8}{'ครั้ง':>6}{'ล้ม':>6}{'เฉลี่ย ms':>12}{'สูงสุด ms':>12}")
    for s in data["steps"]:
        say(f"  {s['step']:<14}{s['type']:<8}{s['runs']:>6}{s['failures']:>6}{s['avg_ms']:>12}{s['max_ms']:>12}")
    if data["errors"]:
        say("\nข้อผิดพลาดที่พบบ่อย")
        for e in data["errors"]:
            say(f"  {e['count']:>3} ครั้ง  {e['error']}")
    if minutes_by_hand is not None:
        say(f"\nถ้าทำมือรายการละ {minutes_by_hand:g} นาที (ตัวเลขที่คุณใส่) งานที่สำเร็จ {data['succeeded']} รายการ"
            f"จะใช้ราว {data['by_hand_minutes']:g} นาที เครื่องใช้ {data['machine_minutes']:g} นาที")
        say("ตัวเลขนี้ยังไม่รวมเวลาที่คุณใช้ตรวจผล และเวลาที่ใช้สร้างกับดูแลงานนี้")
    if db_path:
        say(f"\nบันทึกฐานข้อมูลไว้ที่ {db_path} เปิดถามต่อด้วย SQL ได้ เช่น: SELECT step, AVG(ms) FROM steps GROUP BY step")
    return 0


# ---------- คำสั่งตั้งเวลา ----------

def schedule_commands(job: str, hope_py: Path, python: str, every_minutes: int, windows: bool | None = None) -> dict:
    """คืนคำสั่งสำหรับให้ระบบปฏิบัติการเรียก auto run ตามรอบ (ไม่ได้ติดตั้งให้ ผู้ใช้เป็นคนรันเอง)"""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", job):
        raise ToolError("ชื่องานที่จะตั้งเวลาต้องเป็นตัวอักษรอังกฤษ ตัวเลข - หรือ _ เท่านั้น")
    if every_minutes < 1 or every_minutes > 1439 or (every_minutes >= 60 and every_minutes % 60):
        raise ToolError("--every-minutes ต้องเป็น 1-59 หรือจำนวนชั่วโมงเต็ม เช่น 60, 120 (ไม่เกิน 1380)")
    windows = os.name == "nt" if windows is None else windows
    name = f"dpsxhope-{job}"
    if windows:
        unit = f"/SC MINUTE /MO {every_minutes}" if every_minutes < 60 else f"/SC HOURLY /MO {every_minutes // 60}"
        run = f'\\"{python}\\" \\"{hope_py}\\" auto run {job}'
        return {"system": "Windows Task Scheduler (รันใน Command Prompt ไม่ใช่ PowerShell)",
                "create": f'schtasks /Create /TN "{name}" {unit} /TR "{run}"',
                "check": f'schtasks /Query /TN "{name}"',
                "remove": f'schtasks /Delete /TN "{name}" /F'}
    when = f"*/{every_minutes} * * * *" if every_minutes < 60 else f"0 */{every_minutes // 60} * * *"
    line = f"{when} cd '{hope_py.parent}' && '{python}' hope.py auto run {job} >> '{hope_py.parent}/auto-{job}.cron.log' 2>&1"
    return {"system": "cron (macOS, Linux)",
            "create": f"(crontab -l 2>/dev/null; echo \"{line}\") | crontab -",
            "check": "crontab -l",
            "remove": f"crontab -l | grep -v 'auto run {job} ' | crontab -"}


def show_schedule(job: str, hope_py: Path, every_minutes: int, say=print, windows: bool | None = None) -> int:
    cmd = schedule_commands(job, hope_py, sys.executable, every_minutes, windows)
    say(f"คำสั่งสำหรับ {cmd['system']}")
    say("โปรแกรมนี้ไม่ได้ตั้งเวลาให้ คัดลอกคำสั่งไปรันเองเมื่อพร้อม\n")
    say(f"ตั้งเวลา:\n  {cmd['create']}\n")
    say(f"ตรวจว่าตั้งแล้ว:\n  {cmd['check']}\n")
    say(f"ยกเลิก:\n  {cmd['remove']}\n")
    say("ก่อนตั้งเวลา ลองรันมือให้ผ่านก่อน: python hope.py auto run " + job)
    say("หมายเหตุ: คำสั่งชุดนี้ยังไม่ได้ทดสอบโดยการตั้งเวลาจริงในคู่มือ ตรวจผลครั้งแรกด้วยตัวเอง")
    return 0


# ---------- ช่องรับไฟล์ทาง HTTP (ให้ n8n หรือโปรแกรมอื่นส่งงานเข้ามา) ----------

def safe_file_name(name, patterns: list[str]) -> str:
    """ชื่อไฟล์ที่รับได้: ไม่มีโฟลเดอร์ ไม่ขึ้นต้นด้วยจุดหรือขีดล่าง และตรงกับ patterns ของงาน"""
    if not isinstance(name, str) or not SAFE_NAME.match(name) or ".." in name:
        raise ToolError("ชื่อไฟล์ใช้ได้เฉพาะตัวอักษร ตัวเลข เว้นวรรค จุด ขีด และขีดล่าง ห้ามมีโฟลเดอร์")
    if not any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns):
        raise ToolError(f"ชื่อไฟล์ต้องตรงกับ {', '.join(patterns)}")
    return name


def make_handler(inbox: Path, patterns: list[str], token: str, max_bytes: int):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code: int, payload: dict):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/inbox":
                return self._send(404, {"error": "not found"})
            given = self.headers.get("Authorization", "")
            if not hmac.compare_digest(given.encode(), f"Bearer {token}".encode()):
                return self._send(401, {"error": "invalid token"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "bad Content-Length"})
            if length <= 0 or length > max_bytes + 4096:
                return self._send(413, {"error": f"body must be 1-{max_bytes} bytes"})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                name = safe_file_name(body.get("name") if isinstance(body, dict) else None, patterns)
                text = body.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ToolError("text ต้องเป็นข้อความที่ไม่ว่าง")
                if len(text.encode("utf-8")) > max_bytes:
                    return self._send(413, {"error": f"text must be at most {max_bytes} bytes"})
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "body must be UTF-8 JSON: {\"name\": \"...\", \"text\": \"...\"}"})
            except ToolError as exc:
                return self._send(400, {"error": str(exc)})
            target = inbox / name
            try:
                with open(target, "x", encoding="utf-8", newline="") as handle:      # "x" = ไม่เขียนทับของเดิม
                    handle.write(text)
            except FileExistsError:
                return self._send(409, {"error": "a file with this name is already waiting"})
            self._send(201, {"saved": name})
    return Handler


def make_server(inbox: Path, patterns: list[str], token: str, max_bytes: int, port: int) -> ThreadingHTTPServer:
    if len(token) < MIN_TOKEN_LENGTH:
        raise ToolError(f"ตั้ง {TOKEN_ENV} เป็นข้อความสุ่มยาวอย่างน้อย {MIN_TOKEN_LENGTH} ตัวอักษรก่อน "
                        "(สร้างได้ด้วย: python -c \"import secrets; print(secrets.token_urlsafe(24))\")")
    inbox.mkdir(parents=True, exist_ok=True)
    # รับเฉพาะจากเครื่องนี้เท่านั้น ถ้าต้องรับจากเครื่องอื่นให้วางหลัง reverse proxy ที่ทำ TLS และตรวจสิทธิ์
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(inbox, patterns, token, max_bytes))
