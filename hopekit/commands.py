"""คำสั่งที่ผู้ใช้เรียกผ่านเมนูหรือ `python hope.py <คำสั่ง>` ทุกฟังก์ชันคืน exit code"""
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import engine, envfile, runner, scaffold, settings
from .ui import ConsoleIO

SUPPORTED = {".txt", ".md", ".pdf"}
RAG_MODULES = runner.PROFILES["rag"]["modules"]
SAMPLES = {"th": "sample_docs_th", "en": "sample_docs"}
# เลขข้อในเมนูหลัก ใช้ร่วมกันเพื่อให้ข้อความแนะนำตรงกับเมนูเสมอ
MENU_KEYS = {"setup": "1", "demo": "2", "docs": "3", "ask": "4", "agent": "5", "settings": "6", "status": "7", "tool": "8", "auto": "9"}
DEMO_QUESTIONS = [
    "ลาพักร้อนได้กี่วันต่อปี และต้องแจ้งล่วงหน้านานแค่ไหน",
    "ถ้าสินค้าแตกเสียหายระหว่างขนส่งต้องทำอย่างไร",
    "ทำโน้ตบุ๊กหายต้องแจ้งฝ่ายไอทีภายในกี่ชั่วโมง",
]
# ซ่อนแถบความคืบหน้าของไลบรารีโมเดลตอนถามตอบ เพื่อให้หน้าจอมีแต่คำถามและคำตอบ
QUIET_ENV = {"TQDM_DISABLE": "1", "HF_HUB_DISABLE_PROGRESS_BARS": "1", "TRANSFORMERS_VERBOSITY": "error"}
CLAUDE_PRIVACY = ("หมายเหตุเรื่องข้อมูล: การค้นหาเอกสารทำในเครื่องของคุณ แต่เมื่อใช้ Claude ข้อความช่วงเอกสารที่เกี่ยวข้อง"
                  "กับคำถามจะถูกส่งไปยัง Anthropic เพื่อสร้างคำตอบ อย่าใส่เอกสารลับหรือข้อมูลส่วนบุคคลถ้าไม่ได้รับอนุญาต "
                  "ถ้าต้องการให้ข้อมูลอยู่ในเครื่องทั้งหมดให้ใช้ Ollama")
HEAVY_NOTE = ("ไลบรารีค้นหา (เช่น PyTorch) มีขนาดใหญ่ อาจดาวน์โหลดหลายร้อย MB ถึงหลาย GB ขึ้นกับเครื่อง "
              "ใช้เวลาหลายนาที และครั้งแรกที่ใช้จะดาวน์โหลดโมเดลค้นหาเพิ่มอีกครั้ง")
DOCS_README = (
    "วางไฟล์เอกสารของคุณที่นี่ (.txt .md .pdf) ใส่โฟลเดอร์ย่อยได้\n"
    "แล้วเปิดเมนู \"ใส่เอกสารของฉัน\" หรือรัน: python hope.py docs\n\n"
    "ข้อควรรู้\n"
    "- ทุกครั้งที่ใส่เอกสาร ระบบจะสร้างดัชนีใหม่จากทุกไฟล์ในโฟลเดอร์ แทนของเดิม\n"
    "- PDF ที่เป็นภาพสแกนอ่านไม่ได้ (ยังไม่รองรับ OCR) ควรใช้ไฟล์ต้นฉบับ .txt หรือ .md ถ้ามี\n"
    "- ไฟล์ที่ชื่อขึ้นต้นด้วย _ หรือ . จะถูกข้าม (ไฟล์นี้ก็ถูกข้าม) ใช้พักไฟล์ที่ยังไม่อยากให้อ่านได้\n"
    "- โฟลเดอร์นี้ไม่ถูกอัปโหลดขึ้น Git\n"
)
DOCS_README_NAME = "_README.txt"


@dataclass
class Context:
    io: object = field(default_factory=ConsoleIO)
    root: Path = runner.ROOT
    run: Callable = runner.run
    resolve: Callable = runner.resolve_python
    models_fn: Callable = engine.ollama_models


# ---------- ตัวช่วย ----------

def env_value(ctx: Context, key: str, default: str | None = None) -> str | None:
    return engine.effective(ctx.root, key, default)


def _save(ctx: Context, key: str, value: str) -> None:
    envfile.set_value(ctx.root / ".env", key, value, template=ctx.root / ".env.example")


def data_dir(ctx: Context) -> Path:
    raw = env_value(ctx, "RAG_DATA_DIR")
    if raw and Path(raw).is_absolute():
        return Path(raw)
    return ctx.root / "rag-pipeline" / (raw or "data")


def index_exists(ctx: Context) -> bool:
    return (data_dir(ctx) / "index_meta.json").exists()


def index_info(ctx: Context) -> tuple[int, int] | None:
    """(จำนวนช่วงเอกสาร, จำนวนไฟล์) ของดัชนีปัจจุบัน หรือ None ถ้ายังไม่มี"""
    try:
        chunks = json.loads((data_dir(ctx) / "index_meta.json").read_text(encoding="utf-8"))
        return len(chunks), len({c.get("source") for c in chunks})
    except Exception:
        return None


def ensure_docs_dir(ctx: Context) -> Path:
    folder = ctx.root / "my-docs"
    folder.mkdir(exist_ok=True)
    readme = folder / DOCS_README_NAME
    if not readme.exists():
        readme.write_text(DOCS_README, encoding="utf-8")
    return folder


def next_step(ctx: Context) -> tuple[str, str]:
    """(รหัสเมนูที่แนะนำ, คำอธิบาย) จากสถานะปัจจุบัน"""
    k = MENU_KEYS
    if not ctx.resolve(RAG_MODULES, ctx.root):
        return k["setup"], f"ยังไม่ได้ติดตั้ง เริ่มที่ข้อ {k['setup']} (ตั้งค่าครั้งแรก)"
    status = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
    if not status.ok:
        return k["settings"], (f"{status.text} ไปที่ข้อ {k['settings']} (ตั้งค่า) "
                               f"หรือลองดูส่วนค้นหาก่อนที่ข้อ {k['demo']}")
    if not index_exists(ctx):
        return k["docs"], (f"ยังไม่มีเอกสาร ไปที่ข้อ {k['docs']} (ใส่เอกสารของฉัน) "
                           f"หรือลองเดโมก่อนที่ข้อ {k['demo']}")
    return k["ask"], f"พร้อมแล้ว ถามคำถามได้ที่ข้อ {k['ask']}"


def _version(cmd: list[str]) -> str:
    exe = shutil.which(cmd[0])
    if not exe:
        return "ไม่พบ"
    try:
        done = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=10)
        return (done.stdout or done.stderr).strip().splitlines()[0]
    except Exception:
        return "พบ แต่อ่านเวอร์ชันไม่ได้"


# ---------- status ----------

def status(ctx: Context) -> int:
    say = ctx.io.say
    say("== เครื่องมือ ==")
    say(f"  python  {sys.version.split()[0]}")
    say(f"  node    {_version(['node', '--version'])}   (ใช้กับ ai-api เท่านั้น)")
    say(f"  git     {_version(['git', '--version'])}")

    say("\n== ไลบรารี ==")
    venv = runner.venv_python(ctx.root)
    say(f"  .venv   {'มี' if venv else 'ยังไม่มี (สร้างตอนตั้งค่าครั้งแรก)'}")
    python = str(venv) if venv else sys.executable
    found = runner.check_modules(python, runner.PROFILES["all"]["modules"])    # เรียก Python ย่อยครั้งเดียว
    for name in ("rag", "agent", "eval"):
        info = runner.PROFILES[name]
        missing = [m for m in info["modules"] if not found.get(m)]
        if not missing:
            say(f"  ครบ         {info['label']}")
        elif len(missing) == len(info["modules"]):
            say(f"  ยังไม่ติดตั้ง {info['label']}  (ถ้าอยากใช้: python hope.py setup --profile {name})")
        else:
            say(f"  ติดตั้งไม่ครบ {info['label']}  (ขาด {', '.join(missing)}) รัน: python hope.py setup --profile {name}")
    say(f"  {'มี  ' if (ctx.root / 'ai-api' / 'node_modules').is_dir() else 'ยังไม่มี'} ai-api/node_modules (npm ci)")

    say("\n== การตั้งค่า ==")
    say(f"  .env    {'มี' if (ctx.root / '.env').exists() else 'ยังไม่มี (สร้างตอนตั้งค่าครั้งแรก)'}")
    for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        say(f"  {key:<18} {'ตั้งแล้ว' if env_value(ctx, key) else 'ยังไม่ตั้ง'}")
    provider = env_value(ctx, "LLM_PROVIDER", "anthropic")
    st = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
    say(f"  AI ที่ใช้ตอบ ({provider}): {'พร้อม' if st.ok else 'ยังไม่พร้อม'} — {st.text}")
    if not st.ok and st.fix:
        say(f"    วิธีแก้: {st.fix}")

    say("\n== เอกสาร ==")
    info = index_info(ctx)
    if info:
        say(f"  มีดัชนีแล้ว {info[1]} ไฟล์ {info[0]} ช่วงเอกสาร")
    else:
        say("  ยังไม่มีดัชนี (ใส่เอกสารก่อนถึงจะถามได้)")

    say("\nดูภาษาและเครื่องมือทั้งหมดของเครื่องนี้: python hope.py stack")
    say(f"ขั้นต่อไป: {next_step(ctx)[1]}")
    return 0


# ---------- setup ----------

WINDOWS_SAFE_ROOT_LENGTH = 70   # ไลบรารีค้นหามีไฟล์ซ้อนลึกกว่า 180 ตัว บวกกับพาธของโฟลเดอร์นี้ต้องไม่เกิน 260


def path_too_deep(root: Path, windows: bool | None = None) -> bool:
    """Windows จำกัดพาธ 260 ตัวอักษรเมื่อไม่ได้เปิด Long Path ซึ่งเป็นค่าเริ่มต้นของเครื่องส่วนใหญ่"""
    windows = os.name == "nt" if windows is None else windows
    return windows and len(str(root)) > WINDOWS_SAFE_ROOT_LENGTH


def _engine_options(profile: str, models: list[str] | None) -> list[tuple[str, str]]:
    ollama = (f"Ollama ในเครื่อง (ฟรี ข้อมูลไม่ออกจากเครื่อง) — พบ {len(models)} โมเดล" if models
              else "Ollama ในเครื่อง (ฟรี) — ยังไม่พบ ต้องติดตั้งและเปิด Ollama ก่อน")
    claude = "Claude API — ต้องมี API key และคิดค่าใช้จ่ายตามการใช้งาน"
    gemini = "Gemini API — ใช้กับ llm-eval เท่านั้น ต้องมี API key"
    if profile in ("agent", "rag"):
        return [("ollama", ollama), ("claude", claude)]
    return [("ollama", ollama), ("claude", claude), ("gemini", gemini)]


def _pick_engine(ctx: Context, profile: str, engine_name: str | None, yes: bool,
                 models: list[str] | None) -> str | None:
    """เลือก AI ที่ใช้ตอบ คืนชื่อ หรือ None ถ้าค่าที่ระบุใช้ไม่ได้ (พร้อมแจ้งเหตุผลแล้ว)"""
    io = ctx.io
    options = _engine_options(profile, models)
    keys = [k for k, _ in options]
    if engine_name is None:
        if len(options) == 1:
            engine_name = keys[0]
            io.say(f"โปรไฟล์นี้ใช้ได้กับ: {options[0][1]}")
        elif yes:
            engine_name = "ollama" if models and "ollama" in keys else "claude"
        else:
            io.say("\nจะให้ AI ตัวไหนตอบคำถาม")
            engine_name = io.choose("เลือก", options, default="ollama" if models else "claude")
    if engine_name not in {"ollama", "claude", "gemini"}:
        io.say(f"ไม่รู้จัก AI แบบ {engine_name} เลือกได้: ollama, claude, gemini")
        return None
    if engine_name not in keys:
        io.say(f"โปรไฟล์ {profile} ใช้กับ {engine_name} ไม่ได้ เลือกได้: {', '.join(keys)}")
        return None
    return engine_name


def _pick_model(ctx: Context, models: list[str] | None, wanted: str | None, yes: bool) -> str:
    """เลือกโมเดลใน Ollama: ที่ระบุมา > ที่เคยตั้งไว้ถ้ามีจริง > ตัวแรกที่พบ (ถามผู้ใช้ถ้าไม่ใช่โหมด yes)"""
    io = ctx.io
    current = env_value(ctx, "OLLAMA_MODEL", "llama3.2") or "llama3.2"
    if wanted:
        model = wanted
    elif models:
        default = current if engine.model_present(models, current) else models[0]
        model = default if yes else io.choose("\nเลือกโมเดลใน Ollama", [(m, m) for m in models], default=default)
    else:
        model = current
    if models is None:
        io.say("หมายเหตุ: ติดต่อ Ollama ไม่ได้ตอนนี้ ตั้งค่าไว้ก่อน แล้วเปิด Ollama ก่อนถามคำถาม")
    elif not engine.model_present(models, model):
        io.say(f"หมายเหตุ: ยังไม่พบโมเดล {model} ใน Ollama ดาวน์โหลดด้วย `ollama pull {model}` ก่อนใช้งาน")
    return model


def _ask_secret(ctx: Context, engine_name: str, skip_prompt: bool) -> tuple[str | None, str | None]:
    """(ชื่อ key, ค่าที่ผู้ใช้ใส่) ของ AI ที่เลือก ค่าเป็น None ถ้ามีอยู่แล้วหรือผู้ใช้ข้าม"""
    io = ctx.io
    if engine_name == "claude":
        io.say(f"\n{CLAUDE_PRIVACY}")
    key = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}.get(engine_name)
    if not key:
        return None, None
    if env_value(ctx, key):
        io.say(f"พบ {key} ตั้งไว้แล้ว จะใช้ค่าเดิม")
    elif skip_prompt:
        io.say(f"ยังไม่ได้ใส่ {key} ใส่ทีหลังได้ด้วย: python hope.py config set {key}")
    else:
        io.say(f"\nวาง {key} (ตอนพิมพ์จะไม่เห็นตัวอักษร) หรือกด Enter เพื่อข้ามไปใส่ทีหลัง")
        return key, io.secret(key) or None
    return key, None


def setup(ctx: Context, profile: str | None = None, engine_name: str | None = None,
          ollama_model: str | None = None, yes: bool = False, no_install: bool = False,
          dry_run: bool = False) -> int:
    io = ctx.io
    io.say("== ตั้งค่าครั้งแรก ==")
    if dry_run:
        io.say("(โหมดลองดู: จะแสดงสิ่งที่จะทำ แต่ไม่เปลี่ยนอะไรในเครื่อง)")

    if profile is None:
        profile = "rag" if yes else io.choose(
            "อยากใช้อะไร", [(k, v["label"]) for k, v in runner.PROFILES.items()], default="rag")
    if profile not in runner.PROFILES:
        io.say(f"ไม่รู้จักโปรไฟล์ {profile} เลือกได้: {', '.join(runner.PROFILES)}")
        return 2

    url = env_value(ctx, "OLLAMA_URL", engine.DEFAULT_OLLAMA_URL) or engine.DEFAULT_OLLAMA_URL
    models = ctx.models_fn(url)
    engine_name = _pick_engine(ctx, profile, engine_name, yes, models)
    if engine_name is None:
        return 2
    model = _pick_model(ctx, models, ollama_model, yes) if engine_name == "ollama" else None
    secret_key, secret_value = _ask_secret(ctx, engine_name, yes or dry_run)

    info = runner.PROFILES[profile]
    io.say("\nจะทำดังนี้")
    step = 1
    if not no_install:
        io.say(f"  {step}. สร้างโฟลเดอร์ .venv (ถ้ายังไม่มี) และติดตั้งไลบรารีสำหรับ \"{info['label']}\"")
        if info["heavy"]:
            io.say(f"     {HEAVY_NOTE}")
        step += 1
    chosen = {"ollama": f"Ollama โมเดล {model}", "claude": "Claude", "gemini": "Gemini"}[engine_name]
    io.say(f"  {step}. ตั้งค่าในไฟล์ .env ให้ใช้ {chosen}")
    step += 1
    io.say(f"  {step}. สร้างโฟลเดอร์ my-docs ไว้ให้วางเอกสารของคุณ")

    if dry_run:
        for command in runner.install_plan(profile, ctx.root):
            io.say("  คำสั่งติดตั้ง: " + " ".join(command))
        return 0
    deep = not no_install and path_too_deep(ctx.root)
    if deep:
        io.say(f"\nคำเตือน: โฟลเดอร์นี้อยู่ลึกเกินไป ({len(str(ctx.root))} ตัวอักษร) Windows จำกัดความยาวพาธไว้ที่ 260 ตัว "
               "และไลบรารีค้นหามีไฟล์ซ้อนลึก การติดตั้งอาจล้มเหลวกลางทาง")
        io.say("แนะนำ: ย้ายโฟลเดอร์ไปไว้ใกล้ราก เช่น C:\\dpsxhope แล้วเปิดใหม่")
        if not yes and not io.confirm("ติดตั้งต่อทั้งที่โฟลเดอร์ลึกไหม", default=False):
            io.say("ยกเลิกแล้ว ไม่มีอะไรเปลี่ยน")
            return 1
    if not yes and not io.confirm("\nเริ่มเลยไหม", default=True):
        io.say("ยกเลิกแล้ว ไม่มีอะไรเปลี่ยน")
        return 1

    if not no_install:
        code = runner.install(profile, ctx.root, runner=ctx.run)
        if code != 0:
            io.say("\nติดตั้งไลบรารีไม่สำเร็จ ดูข้อความด้านบน (มักเกิดจากอินเทอร์เน็ตหรือ Python เวอร์ชันไม่รองรับ)")
            io.say("ถ้าเป็น Linux และข้อความพูดถึง venv หรือ ensurepip ให้ติดตั้งก่อน: sudo apt install python3-venv")
            io.say("ถ้าเป็น Windows และข้อความพูดถึง Long Path ให้ย้ายโฟลเดอร์ไปไว้ใกล้ราก เช่น C:\\dpsxhope")
            io.say("แก้แล้วรันใหม่ได้เลย: python hope.py setup")
            return code

    try:
        if engine_name == "ollama":
            _save(ctx, "LLM_PROVIDER", "ollama")
            _save(ctx, "OLLAMA_MODEL", model)
        elif engine_name == "claude":
            _save(ctx, "LLM_PROVIDER", "anthropic")
        if secret_key and secret_value:
            _save(ctx, secret_key, secret_value)
        ensure_docs_dir(ctx)
    except OSError as exc:
        io.say(f"เขียนไฟล์ในโฟลเดอร์นี้ไม่ได้ ({exc}) ย้ายโปรแกรมไปไว้ในโฟลเดอร์ที่แก้ไขไฟล์ได้ แล้วรันใหม่")
        return 1
    if secret_key and secret_value:
        io.say(f"บันทึก {secret_key} ลงไฟล์ .env แล้ว (ไฟล์นี้ไม่ถูกอัปโหลดขึ้น Git อย่าส่งต่อให้ใคร)")

    io.say("\nตั้งค่าเสร็จแล้ว")
    io.say(f"ขั้นต่อไป: {next_step(ctx)[1]}")
    return 0


# ---------- docs / ask / agent ----------

def _not_installed(ctx: Context, what: str = "ถามตอบจากเอกสาร") -> int:
    ctx.io.say(f"ยังไม่ได้ติดตั้งไลบรารีสำหรับ \"{what}\"")
    ctx.io.say("เริ่มที่: python hope.py setup (หรือเมนูข้อ 1)")
    return 1


def docs(ctx: Context, folder: str | None = None, sample: str | None = None) -> int:
    io = ctx.io
    python = ctx.resolve(RAG_MODULES, ctx.root)
    if not python:
        return _not_installed(ctx)

    if sample:
        if sample not in SAMPLES:
            io.say(f"ตัวอย่างที่มี: {', '.join(SAMPLES)} (th = ภาษาไทย, en = อังกฤษ)")
            return 2
        path = ctx.root / "rag-pipeline" / SAMPLES[sample]
    elif folder:
        path = Path(folder.strip().strip("\"'")).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
    else:
        path = ensure_docs_dir(ctx)

    if not path.is_dir():
        io.say(f"ไม่พบโฟลเดอร์: {path}")
        io.say("ตรวจชื่อ/ที่อยู่อีกครั้ง หรือวางไฟล์ในโฟลเดอร์ my-docs แล้วเลือกใหม่")
        return 2
    files = [p for p in path.rglob("*")
             if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith(("_", "."))]
    if not files:
        io.say(f"ยังไม่มีไฟล์ .txt .md หรือ .pdf ใน {path}")
        io.say("วางไฟล์แล้วเลือกใหม่ หรือลองกับเอกสารตัวอย่างก่อน: python hope.py docs --sample th")
        return 2

    io.say(f"พบ {len(files)} ไฟล์ใน {path}")
    io.say("จะสร้างดัชนีใหม่จากทุกไฟล์ในโฟลเดอร์นี้ แทนดัชนีเดิม")
    if not index_exists(ctx):
        io.say("ครั้งแรกอาจดาวน์โหลดโมเดลค้นหา ใช้เวลาสักครู่และต้องต่ออินเทอร์เน็ต")
    if any(p.suffix.lower() == ".pdf" for p in files):
        io.say("หมายเหตุ: PDF ที่เป็นภาพสแกนอ่านไม่ได้ และ PDF ภาษาไทยบางไฟล์อาจขาดวรรณยุกต์")
    code = ctx.run([python, "pipeline.py", "ingest", "--docs", str(path)], cwd=ctx.root / "rag-pipeline")
    if code == 0:
        io.say(f"\nเสร็จแล้ว ถามคำถามได้ด้วย: python hope.py ask (หรือเมนูข้อ {MENU_KEYS['ask']})")
    else:
        io.say("\nสร้างดัชนีไม่สำเร็จ ดูข้อความด้านบน")
    return code


def demo(ctx: Context) -> int:
    """ลองดูใน 1-2 นาที: ใช้เอกสารตัวอย่างในดัชนีแยก จึงไม่แตะดัชนีของผู้ใช้
    ถ้า AI ที่ใช้ตอบยังไม่พร้อม จะโชว์เฉพาะส่วนค้นหา (ไม่ต้องมี key และไม่ต้องมี Ollama)"""
    io = ctx.io
    python = ctx.resolve(RAG_MODULES, ctx.root)
    if not python:
        return _not_installed(ctx)
    st = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
    demo_data = ctx.root / "rag-pipeline" / "data-demo"
    env = {"RAG_DATA_DIR": str(demo_data)}
    cwd = ctx.root / "rag-pipeline"
    io.say("== เดโม ==")
    io.say("ใช้เอกสารตัวอย่างสมมติ (นโยบายพนักงาน, ไอที, การคืนสินค้า, ค่าเดินทาง ฯลฯ) และไม่แตะเอกสารของคุณ")
    if st.ok:
        io.say("AI ที่ใช้ตอบพร้อมแล้ว จะแสดงคำตอบพร้อมแหล่งอ้างอิง")
    else:
        io.say(f"AI ที่ใช้ตอบยังไม่พร้อม ({st.text}) จึงแสดงเฉพาะส่วนค้นหาที่เจอช่วงเอกสารที่เกี่ยวข้อง")
    if not (demo_data / "index_meta.json").exists():
        io.say("\nกำลังสร้างดัชนีจากเอกสารตัวอย่าง (ครั้งแรกอาจดาวน์โหลดโมเดลค้นหา ใช้เวลาสักครู่)")
        code = ctx.run([python, "pipeline.py", "ingest", "--docs", str(cwd / SAMPLES["th"])], cwd=cwd, env_extra=env)
        if code != 0:
            io.say("สร้างดัชนีเดโมไม่สำเร็จ ดูข้อความด้านบน")
            return code
    if st.ok:
        io.say("หมายเหตุ: ถ้าเครื่องไม่มี GPU คำตอบจาก AI อาจใช้เวลาหลายนาทีต่อข้อ (กด Ctrl+C เพื่อหยุด)")
    io.say("\nคำถามตัวอย่าง:")
    for question in DEMO_QUESTIONS:
        io.say(f"  - {question}")
    args = [python, "pipeline.py", "chat"] + ([] if st.ok else ["--search-only"])
    code = ctx.run(args, cwd=cwd, env_extra={**env, **QUIET_ENV}, stdin_text="\n".join(DEMO_QUESTIONS) + "\n")
    if code == 0:
        io.say(f"\nอยากลองกับเอกสารของคุณเอง: เมนูข้อ {MENU_KEYS['docs']} (python hope.py docs)")
    return code


def ask(ctx: Context, question: str | None = None, top_k: int | None = None) -> int:
    io = ctx.io
    python = ctx.resolve(RAG_MODULES, ctx.root)
    if not python:
        return _not_installed(ctx)
    if not index_exists(ctx):
        io.say("ยังไม่มีเอกสารที่ค้นได้")
        io.say("ใส่เอกสารก่อน: python hope.py docs (หรือลองตัวอย่าง: python hope.py docs --sample th)")
        return 1
    st = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
    if not st.ok:
        io.say(f"AI ที่ใช้ตอบยังไม่พร้อม: {st.text}")
        io.say(f"วิธีแก้: {st.fix}")
        return 1
    args = [python, "pipeline.py", "query", question] if question else [python, "pipeline.py", "chat"]
    if top_k:
        args += ["--top-k", str(top_k)]
    return ctx.run(args, cwd=ctx.root / "rag-pipeline", env_extra=QUIET_ENV)


def agent(ctx: Context, task: str | None = None, tools: str | None = None) -> int:
    io = ctx.io
    # agent กับ Ollama ใช้ไลบรารีมาตรฐานอย่างเดียว จึงไม่ต้องติดตั้งอะไรเพิ่ม
    local = (env_value(ctx, "LLM_PROVIDER", "anthropic") or "").lower() == "ollama"
    python = ctx.resolve([] if local else runner.PROFILES["agent"]["modules"], ctx.root)
    if not python:
        return _not_installed(ctx, runner.PROFILES["agent"]["label"])
    st = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
    if not st.ok:
        io.say(f"AI ที่ใช้กับ agent ยังไม่พร้อม: {st.text}")
        if st.fix:
            io.say(f"วิธีแก้: {st.fix}")
        io.say("agent ใช้ได้ทั้ง Claude และ Ollama ในเครื่อง (ต้องเป็นโมเดลที่รองรับ tools ดูได้ที่ python hope.py stack)")
        return 1
    available = scaffold.existing_tools(ctx.root / "agent-kit" / "tools")
    if not task:
        io.say(f"tool ที่มีให้: {', '.join(available) or 'ยังไม่มี'}")
        task = io.ask("ให้ agent ทำอะไร")
        if not task:
            io.say("ยังไม่ได้ใส่งาน")
            return 2
    args = [python, "agent.py"] + (["--tools", tools] if tools else []) + [task]
    return ctx.run(args, cwd=ctx.root / "agent-kit")


def auto_jobs(ctx: Context) -> list[tuple[str, str]]:
    """(ชื่อไฟล์งาน, คำอธิบาย) ของงานอัตโนมัติใน agent-kit/jobs"""
    found = []
    for path in sorted((ctx.root / "agent-kit" / "jobs").glob("*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        uses_ai = any(s.get("type") == "llm" for s in job.get("steps", []) if isinstance(s, dict))
        found.append((path.stem, f"{job.get('description', path.stem)}{' [ใช้ AI]' if uses_ai else ''}"))
    return found


def auto(ctx: Context, job: str, action: str = "run", dry_run: bool = False) -> int:
    """รันงานอัตโนมัติหนึ่งรอบ (หรือ check) ด้วย Python ของ .venv ถ้ามี"""
    python = runner.venv_python(ctx.root) or sys.executable
    args = [python, ctx.root / "agent-kit" / "automate.py", action, job] + (["--dry-run"] if dry_run else [])
    return ctx.run(args, cwd=ctx.root)


def new_tool(ctx: Context, name: str) -> int:
    io = ctx.io
    try:
        path = scaffold.new_tool(name, ctx.root / "agent-kit" / "tools")
    except ValueError as exc:
        io.say(str(exc))
        return 2
    rel = path.relative_to(ctx.root).as_posix()
    io.say(f"สร้างแล้ว: {rel}")
    io.say("ขั้นต่อไป: เปิดไฟล์นั้นแล้วแก้ 3 จุด")
    io.say("  1. ฟังก์ชัน (ทำงานจริงของ tool) และค่าที่คืน ต้องเป็น dict ที่แปลงเป็น JSON ได้")
    io.say("  2. TOOL_SCHEMA > description และ properties (บอก AI ว่า tool นี้ทำอะไร รับอะไร)")
    io.say("  3. REQUIRES_APPROVAL = True ถ้า tool แก้ข้อมูล ส่งข้อความ หรือจ่ายเงิน")
    io.say(f"ลองใช้: python hope.py agent --tools {name} \"งานที่ต้องการ\"")
    return 0


# ---------- config ----------

def _current(ctx: Context):
    return lambda key: env_value(ctx, key)


def display_value(ctx: Context, s: settings.Setting) -> str:
    """ค่าที่แสดงให้ผู้ใช้เห็น: ค่าลับไม่แสดงตัวอักษร ค่าที่ยังไม่ตั้งบอกว่าใช้ค่าเริ่มต้น"""
    value = env_value(ctx, s.key)
    if s.kind == "secret":
        return "ตั้งแล้ว" if value else "ยังไม่ตั้ง"
    return value if value is not None else f"{s.default}  (ค่าเริ่มต้น)"


def config_list(ctx: Context, show_all: bool = False) -> int:
    say = ctx.io.say
    groups = [settings.BASIC] + ([settings.ADVANCED] if show_all else [])
    for group in groups:
        say(f"== {group} ==")
        for s in settings.SETTINGS:
            if s.group == group:
                say(f"  {s.key:<22} {display_value(ctx, s)}")
                say(f"  {'':<22} {s.label}")
    if not show_all:
        say("\nดูค่าขั้นสูงทั้งหมด: python hope.py config --all")
    say("เปลี่ยนค่า: python hope.py config set <ชื่อ> <ค่า>   ลบ: python hope.py config unset <ชื่อ>")
    return 0


def config_get(ctx: Context, key: str) -> int:
    try:
        s = settings.find(key)
    except ValueError as exc:
        ctx.io.say(str(exc))
        return 2
    ctx.io.say(display_value(ctx, s))
    return 0


def config_set(ctx: Context, key: str, value: str | None = None) -> int:
    io = ctx.io
    try:
        s = settings.find(key)
        if value is None:
            if s.kind == "secret":
                value = io.secret(f"วางค่า {s.key} (จะไม่เห็นตัวอักษร)")
            else:
                value = io.ask(f"ค่าใหม่ของ {s.key}", env_value(ctx, s.key) or s.default)
        clean = settings.validate(s.key, value, _current(ctx))
        _save(ctx, s.key, clean)
    except ValueError as exc:
        io.say(str(exc))
        return 2
    except OSError as exc:
        io.say(f"เขียนไฟล์ .env ไม่ได้ ({exc}) ย้ายโปรแกรมไปไว้ในโฟลเดอร์ที่แก้ไขไฟล์ได้แล้วลองใหม่")
        return 1
    shown ="(ไม่แสดงค่า)" if s.kind == "secret" else clean
    io.say(f"ตั้ง {s.key} = {shown} แล้ว")
    if os.environ.get(s.key) and os.environ[s.key] != clean:
        io.say(f"หมายเหตุ: มี environment variable {s.key} ตั้งไว้ในเครื่อง จะทับค่าในไฟล์ .env")
    if s.reingest:
        io.say(f"ค่านี้มีผลตอนสร้างดัชนี ใส่เอกสารใหม่อีกครั้ง (เมนูข้อ {MENU_KEYS['docs']}) ถึงจะใช้ค่าใหม่")
    if s.key in {"LLM_PROVIDER", "OLLAMA_MODEL", "OLLAMA_URL"}:
        st = engine.engine_status(ctx.root, models_fn=ctx.models_fn)
        io.say(f"สถานะ AI ที่ใช้ตอบ: {st.text}" + ("" if st.ok else f" (วิธีแก้: {st.fix})"))
    return 0


def config_unset(ctx: Context, key: str) -> int:
    try:
        s = settings.find(key)
    except ValueError as exc:
        ctx.io.say(str(exc))
        return 2
    removed = envfile.unset(ctx.root / ".env", s.key)
    ctx.io.say(f"ลบ {s.key} ออกจาก .env แล้ว" if removed else f"{s.key} ไม่ได้ตั้งไว้ใน .env อยู่แล้ว")
    return 0
