"""
automate.py — งานอัตโนมัติจากไฟล์ JSON: เฝ้าโฟลเดอร์หรือรันตามรอบ แล้วทำทีละขั้น

  python automate.py list                          งานตัวอย่างในโฟลเดอร์ jobs/
  python automate.py check inbox-todo              ตรวจไฟล์งานว่าถูกต้องไหม (บอกทุกจุดที่ผิด)
  python automate.py run inbox-todo --dry-run      ดูก่อนว่าจะทำอะไร โดยไม่ทำจริง
  python automate.py run inbox-todo                ทำหนึ่งรอบแล้วจบ (เหมาะกับ Task Scheduler หรือ cron)
  python automate.py loop inbox-todo               ทำซ้ำทุก every_seconds จนกด Ctrl+C
  python automate.py report inbox-todo             สรุปจาก log: สำเร็จ ล้ม เวลาต่อขั้น (ใช้ SQLite)
  python automate.py schedule inbox-todo --every-minutes 15   แสดงคำสั่งตั้งเวลาของระบบปฏิบัติการ
  python automate.py serve inbox-todo              เปิดช่องรับไฟล์ทาง HTTP ในเครื่อง (ให้ n8n หรือโปรแกรมอื่นส่งเข้ามา)

ขั้นมี 3 ชนิด: tool (เรียก tool ในโฟลเดอร์ tools/), llm (ถามโมเดล), write (เขียนไฟล์)
ขั้นชนิด tool และ write ใช้ไลบรารีมาตรฐานอย่างเดียว ไม่ต้องติดตั้งอะไรและไม่ต้องมี AI
กติกาความปลอดภัยอยู่ใน README.md หัวข้อ "งานอัตโนมัติ"
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import autotools  # noqa: E402
import llm  # noqa: E402
import tools as registry  # noqa: E402

JOBS_DIR = HERE / "jobs"
TRIGGERS = ("manual", "watch", "interval")
STEP_TYPES = ("tool", "llm", "write")
BUILTIN_VARS = ("input", "file_name", "file_stem", "file_text", "date", "time", "job")
DEFAULT_LIMITS = {"max_items": 20, "max_file_kb": 256, "max_input_chars": 20000, "max_attempts": 3}
LOCK_STALE_SECONDS = 3600
VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\}")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class JobError(Exception):
    """ไฟล์งานผิด หรือขั้นหนึ่งทำไม่สำเร็จ"""


# ---------- แม่แบบข้อความ ----------

class Pending(str):
    """ค่าที่ยังไม่มีจริงตอน --dry-run ใช้แทนผลของขั้นที่ยังไม่ได้รัน"""


def lookup(name: str, variables: dict):
    value = variables[name.split(".")[0]]
    for part in name.split(".")[1:]:
        if isinstance(value, Pending):
            return value
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise JobError(f"ไม่พบ ${{{name}}} (ไม่มีช่อง {part})")
    return value


def render(template, variables: dict):
    """แทน ${ชื่อ} หรือ ${ขั้น.ช่อง} ในข้อความ รวมถึงข้อความที่อยู่ใน dict และ list"""
    if isinstance(template, dict):
        return {k: render(v, variables) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, variables) for v in template]
    if not isinstance(template, str):
        return template

    def swap(match):
        value = lookup(match.group(1), variables)
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return VAR.sub(swap, template)


def names_in(template) -> set[str]:
    if isinstance(template, dict):
        return set().union(*(names_in(v) for v in template.values())) if template else set()
    if isinstance(template, list):
        return set().union(*(names_in(v) for v in template)) if template else set()
    return {m.split(".")[0] for m in VAR.findall(template)} if isinstance(template, str) else set()


# ---------- ตรวจไฟล์งาน ----------

def limits_of(job: dict) -> dict:
    return {**DEFAULT_LIMITS, **(job.get("limits") or {})}


def validate(job, available_tools: dict | None = None) -> list[str]:
    """คืนรายการปัญหาทั้งหมดของไฟล์งาน (ว่าง = ใช้ได้)"""
    if not isinstance(job, dict):
        return ["ไฟล์งานต้องเป็น JSON object"]
    available = registry.discover() if available_tools is None else available_tools
    problems: list[str] = []
    if not isinstance(job.get("name"), str) or not job.get("name"):
        problems.append("ต้องมี name เป็นข้อความ")

    trigger = job.get("trigger")
    kind = trigger.get("type") if isinstance(trigger, dict) else None
    if kind not in TRIGGERS:
        problems.append(f"trigger.type ต้องเป็นหนึ่งใน {', '.join(TRIGGERS)}")
    else:
        if kind == "watch":
            if not isinstance(trigger.get("folder"), str) or not trigger.get("folder"):
                problems.append("trigger แบบ watch ต้องมี folder")
            patterns = trigger.get("patterns", ["*.txt", "*.md"])
            if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) for p in patterns):
                problems.append("trigger.patterns ต้องเป็นรายการข้อความ เช่น [\"*.txt\"]")
            if trigger.get("after", "keep") not in ("keep", "move"):
                problems.append("trigger.after ต้องเป็น keep หรือ move")
        if kind in ("watch", "interval"):
            every = trigger.get("every_seconds", 60)
            if isinstance(every, bool) or not isinstance(every, (int, float)) or every < 5:
                problems.append("trigger.every_seconds ต้องเป็นตัวเลขตั้งแต่ 5 ขึ้นไป")

    allow = job.get("allow_tools", [])
    if not isinstance(allow, list) or not all(isinstance(a, str) for a in allow):
        problems.append("allow_tools ต้องเป็นรายการชื่อ tool")
        allow = []
    for key, value in (job.get("limits") or {}).items():
        if key not in DEFAULT_LIMITS:
            problems.append(f"limits.{key} ไม่รู้จัก (มี: {', '.join(DEFAULT_LIMITS)})")
        elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
            problems.append(f"limits.{key} ต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป")

    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        return problems + ["ต้องมี steps อย่างน้อยหนึ่งขั้น"]
    known = set(BUILTIN_VARS)
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            problems.append(f"ขั้นที่ {i}: ต้องเป็น object")
            continue
        name = step.get("name")
        where = f"ขั้น {name or i}"
        if not isinstance(name, str) or not NAME.match(name):
            problems.append(f"ขั้นที่ {i}: name ต้องเป็นตัวพิมพ์เล็ก ตัวเลข หรือ _ และขึ้นต้นด้วยตัวอักษร")
        elif name in known:
            problems.append(f"{where}: ชื่อซ้ำกับขั้นก่อนหน้าหรือตัวแปรของระบบ")
        if step.get("on_error", "stop") not in ("stop", "skip"):
            problems.append(f"{where}: on_error ต้องเป็น stop หรือ skip")
        kind = step.get("type")
        used: set[str] = set()
        if kind == "tool":
            tool = step.get("tool")
            if tool not in available:
                problems.append(f"{where}: ไม่พบ tool {tool} (มี: {', '.join(sorted(available)) or '-'})")
            elif available[tool].requires_approval and tool not in allow:
                problems.append(f"{where}: tool {tool} ต้องมีคนอนุมัติ ถ้าตั้งใจให้รันเองให้ใส่ชื่อใน allow_tools")
            if not isinstance(step.get("args", {}), dict):
                problems.append(f"{where}: args ต้องเป็น object")
            used = names_in(step.get("args", {}))
        elif kind == "llm":
            if not isinstance(step.get("prompt"), str) or not step.get("prompt"):
                problems.append(f"{where}: ต้องมี prompt")
            for tool in step.get("tools", []) if isinstance(step.get("tools", []), list) else ["?"]:
                if tool not in available:
                    problems.append(f"{where}: ไม่พบ tool {tool}")
                elif available[tool].requires_approval and tool not in allow:
                    problems.append(f"{where}: tool {tool} ต้องมีคนอนุมัติ ถ้าตั้งใจให้รันเองให้ใส่ชื่อใน allow_tools")
            used = names_in([step.get("prompt", ""), step.get("system", "")])
        elif kind == "write":
            for key in ("path", "content"):
                if not isinstance(step.get(key), str) or not step.get(key):
                    problems.append(f"{where}: ต้องมี {key}")
            used = names_in([step.get("path", ""), step.get("content", "")])
        else:
            problems.append(f"{where}: type ต้องเป็นหนึ่งใน {', '.join(STEP_TYPES)}")
        for unknown in sorted(used - known):
            problems.append(f"{where}: ใช้ ${{{unknown}}} ที่ยังไม่มี (ตัวแปรของระบบ: {', '.join(BUILTIN_VARS)} "
                            "และชื่อขั้นก่อนหน้า)")
        if isinstance(name, str):
            known.add(name)
    return problems


def find_job(ref: str) -> Path:
    path = Path(ref)
    if path.is_file():
        return path.resolve()
    for candidate in (JOBS_DIR / ref, JOBS_DIR / f"{ref}.json"):
        if candidate.is_file():
            return candidate
    raise JobError(f"ไม่พบไฟล์งาน {ref} (ดูรายการด้วย: python automate.py list)")


def load_job(path: Path) -> dict:
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JobError(f"อ่านไฟล์งาน {path} ไม่ได้: {exc}") from exc
    problems = validate(job)
    if problems:
        raise JobError("ไฟล์งานมีปัญหา:\n" + "\n".join(f"  - {p}" for p in problems))
    return job


def default_workdir(job_path: Path) -> Path:
    return job_path.parent / "work" / job_path.stem


# ---------- พื้นที่ทำงาน สถานะ และ log ----------

def inside(workdir: Path, relative: str) -> Path:
    """คืนที่อยู่จริงของไฟล์ในพื้นที่ทำงาน ปฏิเสธที่อยู่ที่ออกนอกพื้นที่"""
    target = (workdir / relative).resolve()
    if not target.is_relative_to(workdir.resolve()):
        raise JobError(f"ที่อยู่ {relative} ออกนอกพื้นที่ทำงาน {workdir}")
    return target


def load_state(workdir: Path) -> dict:
    try:
        state = json.loads((workdir / ".state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state.setdefault("done", {})
    state.setdefault("failed", {})
    return state


def save_state(workdir: Path, state: dict) -> None:
    tmp = workdir / ".state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, workdir / ".state.json")


def log_step(workdir: Path, entry: dict) -> None:
    path = workdir / "logs" / "automation.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}, ensure_ascii=False) + "\n")


class Lock:
    """กันไม่ให้งานเดียวกันรันซ้อนสองรอบ ล็อกที่ค้างเกิน 1 ชั่วโมงถือว่าหมดอายุ"""

    def __init__(self, workdir: Path):
        self.path = workdir / ".lock"

    def __enter__(self):
        try:
            if time.time() - self.path.stat().st_mtime > LOCK_STALE_SECONDS:
                self.path.unlink()
        except OSError:
            pass
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise JobError(f"งานนี้กำลังรันอยู่ในอีกหน้าต่างหนึ่ง (ถ้าไม่ใช่ ให้ลบไฟล์ {self.path})") from None
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass


# ---------- รายการที่ต้องทำ ----------

def pending_items(job: dict, workdir: Path, state: dict, user_input: str = "",
                  retry_failed: bool = False) -> tuple[list[dict], list[str]]:
    """คืน (รายการที่จะทำในรอบนี้, ข้อความแจ้งสิ่งที่ข้าม)"""
    trigger = job["trigger"]
    if trigger["type"] != "watch":
        return [{"key": None, "label": "(รันหนึ่งครั้ง)", "vars": {"input": user_input}}], []

    limits = limits_of(job)
    folder = inside(workdir, trigger["folder"])
    folder.mkdir(parents=True, exist_ok=True)
    patterns = trigger.get("patterns", ["*.txt", "*.md"])
    items, notes = [], []
    for path in sorted(p for p in folder.iterdir() if p.is_file()):
        if path.name.startswith((".", "_")) or not any(fnmatch.fnmatch(path.name.lower(), p.lower()) for p in patterns):
            continue
        data = path.read_bytes()
        key = f"{path.name}:{hashlib.sha256(data).hexdigest()[:16]}"
        if key in state["done"]:
            continue
        failed = state["failed"].get(key)
        if failed and not retry_failed and failed["attempts"] >= limits["max_attempts"]:
            notes.append(f"ข้าม {path.name}: ล้มครบ {failed['attempts']} ครั้งแล้ว ({failed['error']}) "
                         "ลองใหม่ได้ด้วย --retry-failed")
            continue
        if len(data) > limits["max_file_kb"] * 1024:
            notes.append(f"ข้าม {path.name}: ใหญ่เกิน {limits['max_file_kb']} KB (ปรับได้ที่ limits.max_file_kb)")
            continue
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            notes.append(f"ข้าม {path.name}: ไม่ใช่ข้อความ UTF-8")
            continue
        if len(text) > limits["max_input_chars"]:
            text = text[:limits["max_input_chars"]] + "\n[ตัดข้อความที่เหลือออกเพราะยาวเกิน limits.max_input_chars]"
        if len(items) >= limits["max_items"]:
            notes.append(f"มีไฟล์รออีก รอบนี้ทำแค่ {limits['max_items']} ไฟล์ (limits.max_items)")
            break
        items.append({"key": key, "label": path.name, "path": path,
                      "vars": {"input": user_input, "file_name": path.name, "file_stem": path.stem, "file_text": text}})
    return items, notes


# ---------- ทำหนึ่งขั้น ----------

def run_step(step: dict, variables: dict, workdir: Path, job: dict, chat_fn=None):
    kind = step["type"]
    preapproved = frozenset(job.get("allow_tools", []))

    def run_tool(tools, name, args):
        return registry.run(tools, name, args, preapproved)

    if kind == "tool":
        result = run_tool(registry.select([step["tool"]]), step["tool"], render(step.get("args", {}), variables))
        if "error" in result:
            raise JobError(str(result["error"]))
        return result
    if kind == "llm":
        prompt = render(step["prompt"], variables)
        system = render(step.get("system", ""), variables)
        max_tokens = int(step.get("max_tokens", 1024))
        if step.get("tools"):
            done = llm.tool_loop(prompt, registry.select(step["tools"]), run_tool, system=system,
                                 max_tokens=max_tokens, model=step.get("model"), chat_fn=chat_fn)
            if not done.finished:
                raise JobError("โมเดลขอเรียก tool ไม่จบภายในจำนวนรอบที่กำหนด")
            text = done.text
        else:
            reply = (chat_fn or llm.chat)([{"role": "user", "content": prompt}], system=system,
                                          max_tokens=max_tokens, model=step.get("model"))
            if reply.truncated:
                raise JobError(f"คำตอบของโมเดลถูกตัดเพราะยาวเกิน max_tokens ({max_tokens}) เพิ่มค่าในขั้นนี้ หรือขอคำตอบที่สั้นลง")
            text = reply.text
        if not text.strip():
            raise JobError("โมเดลตอบกลับมาว่างเปล่า")
        return text.strip()
    target = inside(workdir, render(step["path"], variables))
    if target.exists() and not step.get("overwrite", False):
        raise JobError(f"มีไฟล์ {target.name} อยู่แล้ว (ตั้ง overwrite เป็น true ถ้าต้องการเขียนทับ)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(step["content"], variables), encoding="utf-8")
    return str(target.relative_to(workdir.resolve())).replace("\\", "/")


def describe_step(step: dict, variables: dict, workdir: Path) -> str:
    """ข้อความสำหรับ --dry-run บอกว่าขั้นนี้จะทำอะไร โดยไม่ทำจริง"""
    kind = step["type"]
    try:
        if kind == "tool":
            args = json.dumps(render(step.get("args", {}), variables), ensure_ascii=False)
            return f"เรียก tool {step['tool']} ด้วย {args[:160]}{'...' if len(args) > 160 else ''}"
        if kind == "llm":
            prompt = render(step["prompt"], variables)
            extra = f" และให้ใช้ tool: {', '.join(step['tools'])}" if step.get("tools") else ""
            return f"ถามโมเดล ({llm.provider()} {llm.model_name(step.get('model'))}) ด้วยข้อความ {len(prompt)} ตัวอักษร{extra}"
        target = inside(workdir, render(step["path"], variables))
        state = "มีอยู่แล้ว " + ("จะเขียนทับ" if step.get("overwrite") else "จะหยุดเพราะไม่ได้ตั้ง overwrite") \
            if target.exists() else "ไฟล์ใหม่"
        return f"เขียนไฟล์ {target.relative_to(workdir.resolve())} ({state})"
    except JobError as exc:
        return f"จะล้ม: {exc}"


# ---------- ทำหนึ่งรอบ ----------

def run_pass(job: dict, workdir: Path, dry_run: bool = False, user_input: str = "", retry_failed: bool = False,
             chat_fn=None, say=print) -> int:
    """ทำหนึ่งรอบ คืนจำนวนรายการที่ล้ม"""
    workdir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return _run_items(job, workdir, True, user_input, retry_failed, chat_fn, say)
    with Lock(workdir):
        return _run_items(job, workdir, False, user_input, retry_failed, chat_fn, say)


def _run_items(job, workdir, dry_run, user_input, retry_failed, chat_fn, say) -> int:
    state = load_state(workdir)
    items, notes = pending_items(job, workdir, state, user_input, retry_failed)
    for note in notes:
        say(f"  ! {note}")
    if not items:
        say("  ไม่มีรายการใหม่")
        return 0
    failures = 0
    for item in items:
        now = time.localtime()
        variables = {"input": "", "file_name": "", "file_stem": "", "file_text": "", "job": job["name"],
                     "date": time.strftime("%Y-%m-%d", now), "time": time.strftime("%H%M%S", now), **item["vars"]}
        say(f"\n▶ {item['label']}")
        error = ""
        for step in job["steps"]:
            name = step["name"]
            if dry_run:
                say(f"   [{name}] {describe_step(step, variables, workdir)}")
                variables[name] = Pending(f"<ผลของขั้น {name}>")
                continue
            started = time.perf_counter()
            try:
                variables[name] = run_step(step, variables, workdir, job, chat_fn)
                ok, problem = True, ""
            except (JobError, llm.EngineError, OSError) as exc:
                ok, problem = False, str(exc)
            log_step(workdir, {"job": job["name"], "item": item["label"], "step": name, "type": step["type"],
                               "ok": ok, "ms": int((time.perf_counter() - started) * 1000),
                               **({"error": problem[:300]} if problem else {})})
            if ok:
                shown = variables[name] if step["type"] == "write" else ""
                say(f"   ✓ [{name}]{' → ' + shown if shown else ''}")
            elif step.get("on_error", "stop") == "skip":
                variables[name] = step.get("default", "")
                say(f"   - [{name}] ข้าม: {problem}")
            else:
                error = f"{name}: {problem}"
                say(f"   ✗ [{name}] {problem}")
                break
        if dry_run:
            continue
        key = item["key"]
        if error:
            failures += 1
            if key:
                attempts = state["failed"].get(key, {}).get("attempts", 0) + 1
                state["failed"][key] = {"attempts": attempts, "error": error[:300]}
        elif key:
            state["failed"].pop(key, None)
            state["done"][key] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if job["trigger"].get("after", "keep") == "move":
                done_dir = inside(workdir, "done")
                done_dir.mkdir(exist_ok=True)
                target = done_dir / item["path"].name
                if target.exists():
                    target = done_dir / f"{item['path'].stem}-{time.strftime('%Y%m%d-%H%M%S')}{item['path'].suffix}"
                os.replace(item["path"], target)
        if key:
            save_state(workdir, state)
    if dry_run:
        say("\n(--dry-run: ยังไม่ได้ทำจริง ไม่ได้เรียกโมเดล ไม่ได้เขียนไฟล์)")
    else:
        say(f"\nสรุป: สำเร็จ {len(items) - failures} ล้ม {failures} | log: {workdir / 'logs' / 'automation.jsonl'}")
    return failures


def run_loop(job: dict, workdir: Path, max_passes: int | None = None, sleep=time.sleep, say=print, **kwargs) -> int:
    every = job["trigger"].get("every_seconds", 60)
    if job["trigger"]["type"] == "manual":
        raise JobError("งานแบบ manual รันได้ทีละครั้งด้วยคำสั่ง run")
    say(f"รันงาน {job['name']} ทุก {every} วินาที กด Ctrl+C เพื่อหยุด")
    passes = failures = 0
    try:
        while max_passes is None or passes < max_passes:
            say(f"\n== รอบที่ {passes + 1} ({time.strftime('%H:%M:%S')}) ==")
            failures += run_pass(job, workdir, say=say, **kwargs)
            passes += 1
            if max_passes is None or passes < max_passes:
                sleep(every)
    except KeyboardInterrupt:
        say("\nหยุดแล้ว")
    return failures


def serve_inbox(job: dict, workdir: Path, port: int) -> int:
    trigger = job["trigger"]
    if trigger["type"] != "watch":
        raise JobError("serve ใช้ได้กับงานแบบ watch เท่านั้น (ต้องมีโฟลเดอร์รับไฟล์)")
    server = autotools.make_server(inside(workdir, trigger["folder"]), trigger.get("patterns", ["*.txt", "*.md"]),
                                   os.getenv(autotools.TOKEN_ENV, ""), limits_of(job)["max_file_kb"] * 1024, port)
    print(f"รับไฟล์ที่ http://127.0.0.1:{server.server_address[1]}/inbox (เฉพาะจากเครื่องนี้) กด Ctrl+C เพื่อหยุด")
    print("ส่งด้วย POST พร้อม header Authorization: Bearer <ค่าใน AUTO_WEBHOOK_TOKEN> และ JSON {\"name\": \"a.txt\", \"text\": \"...\"}")
    print("ช่องนี้แค่รับไฟล์ลงโฟลเดอร์ ต้องเปิด auto loop อีกหน้าต่างหนึ่งเพื่อให้งานทำ")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")
    finally:
        server.server_close()
    return 0


# ---------- CLI ----------

def cmd_list() -> int:
    files = sorted(JOBS_DIR.glob("*.json"))
    if not files:
        print("ยังไม่มีไฟล์งานใน jobs/")
    for path in files:
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            trigger = job.get("trigger", {})
            needs_ai = any(s.get("type") == "llm" for s in job.get("steps", []))
            print(f"{path.stem:<16} [{trigger.get('type', '?')}{', ใช้ AI' if needs_ai else ', ไม่ใช้ AI'}] "
                  f"{job.get('description', job.get('name', ''))}")
        except ValueError as exc:
            print(f"{path.stem:<16} อ่านไม่ได้: {exc}")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    llm.load_env()

    parser = argparse.ArgumentParser(description="งานอัตโนมัติจากไฟล์ JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="งานตัวอย่างใน jobs/")
    for name, text in (("check", "ตรวจไฟล์งาน"), ("run", "ทำหนึ่งรอบ"), ("loop", "ทำซ้ำตามรอบ"),
                       ("report", "สรุปจาก log"), ("schedule", "แสดงคำสั่งตั้งเวลา"), ("serve", "เปิดช่องรับไฟล์ทาง HTTP")):
        p = sub.add_parser(name, help=text)
        p.add_argument("job", help="ชื่องานใน jobs/ หรือที่อยู่ไฟล์ .json")
        p.add_argument("--workdir", type=Path, help="พื้นที่ทำงาน (ค่าเริ่มต้น: jobs/work/<ชื่องาน>)")
        if name == "report":
            p.add_argument("--minutes-by-hand", type=float, help="ถ้าทำมือ ใช้กี่นาทีต่อรายการ (ตัวเลขของคุณเอง)")
            p.add_argument("--db", type=Path, help="บันทึกเป็นไฟล์ SQLite ไว้ถามต่อด้วย SQL")
            p.add_argument("--json", action="store_true")
        if name == "schedule":
            p.add_argument("--every-minutes", type=int, default=15, help="1-59 หรือชั่วโมงเต็ม เช่น 60, 120")
        if name == "serve":
            p.add_argument("--port", type=int, default=8765)
        if name in ("run", "loop"):
            p.add_argument("--input", default="", help="ข้อความที่ส่งเข้า ${input}")
            p.add_argument("--retry-failed", action="store_true", help="ลองไฟล์ที่ล้มครบจำนวนครั้งแล้วอีกรอบ")
        if name == "run":
            p.add_argument("--dry-run", action="store_true", help="ดูว่าจะทำอะไร โดยไม่ทำจริง")
        if name == "loop":
            p.add_argument("--max-passes", type=int, help="หยุดเองเมื่อครบจำนวนรอบ")
    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    try:
        path = find_job(args.job)
        job = load_job(path)
        workdir = (args.workdir or default_workdir(path)).resolve()
        if args.command == "check":
            trigger = job["trigger"]
            print(f"ไฟล์งานถูกต้อง: {job['name']} ({len(job['steps'])} ขั้น, trigger {trigger['type']})")
            print(f"พื้นที่ทำงาน: {workdir}")
            if trigger["type"] == "watch":
                print(f"วางไฟล์ที่: {workdir / trigger['folder']}")
            return 0
        if args.command == "report":
            return autotools.report(workdir, minutes_by_hand=args.minutes_by_hand, db_path=args.db, as_json=args.json)
        if args.command == "schedule":
            return autotools.show_schedule(path.stem, HERE.parent / "hope.py", args.every_minutes)
        if args.command == "serve":
            return serve_inbox(job, workdir, args.port)
        if args.command == "run":
            return 1 if run_pass(job, workdir, args.dry_run, args.input, args.retry_failed) else 0
        return 1 if run_loop(job, workdir, args.max_passes, user_input=args.input,
                             retry_failed=args.retry_failed) else 0
    except (JobError, autotools.ToolError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
