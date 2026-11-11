"""รายการค่าที่ปรับได้ผ่าน `hope.py config` พร้อมตรวจความถูกต้องก่อนเขียนลง .env"""
import difflib
from dataclasses import dataclass
from typing import Callable

BASIC = "ใช้บ่อย"
ADVANCED = "ขั้นสูง"


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    kind: str                       # choice | int | bool | text | secret
    default: str
    choices: tuple = ()
    lo: int | None = None
    hi: int | None = None
    group: str = BASIC
    reingest: bool = False          # เปลี่ยนแล้วต้องใส่เอกสารใหม่ index จึงจะตรง
    note: str = ""


SETTINGS = [
    Setting("LLM_PROVIDER", "AI ที่ใช้ตอบ (ถามเอกสาร agent และงานอัตโนมัติ)", "choice", "anthropic",
            choices=("anthropic", "ollama"), note="anthropic = Claude (ต้องมี key), ollama = โมเดลในเครื่อง"),
    Setting("OLLAMA_MODEL", "ชื่อโมเดลใน Ollama", "text", "llama3.2"),
    Setting("CLAUDE_MODEL", "ชื่อโมเดล Claude", "text", "claude-haiku-5-5"),
    Setting("ANTHROPIC_API_KEY", "Claude API key", "secret", ""),
    Setting("GEMINI_API_KEY", "Gemini API key (ใช้กับ llm-eval)", "secret", ""),
    Setting("GEMINI_MODEL", "ชื่อโมเดล Gemini", "text", "gemini-3.5-flash"),
    Setting("RAG_TOP_K", "จำนวนช่วงเอกสารที่ส่งให้ AI อ่านต่อคำถาม", "int", "4", lo=1, hi=20,
            note="มากขึ้น = ได้บริบทมากขึ้นแต่ช้าและแพงขึ้น"),
    Setting("AGENT_MAX_TURNS", "จำนวนรอบสูงสุดที่ agent ทำงานต่อหนึ่งงาน", "int", "8", lo=1, hi=50),
    Setting("RAG_CHUNK_SIZE", "ขนาดช่วงเอกสารที่ตัด (ตัวอักษร)", "int", "512", lo=100, hi=4000,
            group=ADVANCED, reingest=True),
    Setting("RAG_CHUNK_OVERLAP", "ส่วนที่ซ้อนกันระหว่างช่วง (ตัวอักษร)", "int", "64", lo=0, hi=1000,
            group=ADVANCED, reingest=True),
    Setting("RAG_EMBED_MODEL", "โมเดลค้นหาความหมาย (embedding)", "text", "paraphrase-multilingual-MiniLM-L12-v2",
            group=ADVANCED, reingest=True, note="ต้องเป็นโมเดลที่รองรับภาษาไทยถ้าเอกสารเป็นภาษาไทย"),
    Setting("RAG_USE_RERANK", "จัดอันดับซ้ำด้วยโมเดลเพิ่ม", "bool", "false", group=ADVANCED,
            note="ดาวน์โหลดโมเดลเพิ่มตอนใช้ครั้งแรก และยังไม่ได้วัดว่าให้ผลดีขึ้นกับเอกสารไทย"),
    Setting("RAG_MAX_TOKENS", "ความยาวคำตอบสูงสุด (token)", "int", "1024", lo=64, hi=8192, group=ADVANCED),
    Setting("OLLAMA_URL", "ที่อยู่ Ollama", "text", "http://localhost:11434", group=ADVANCED),
    Setting("HOST", "ai-api: ที่อยู่ที่เปิดรับ", "text", "127.0.0.1", group=ADVANCED,
            note="เปลี่ยนเป็น 0.0.0.0 ต้องตั้ง APP_API_KEY ด้วย"),
    Setting("PORT", "ai-api: พอร์ต", "int", "3000", lo=1, hi=65535, group=ADVANCED),
    Setting("APP_API_KEY", "ai-api: รหัสที่ client ต้องส่งมา", "secret", "", group=ADVANCED),
    Setting("ALLOWED_ORIGINS", "ai-api: เว็บที่อนุญาตเรียก (คั่นด้วย comma)", "text", "", group=ADVANCED),
    Setting("RATE_LIMIT_PER_MINUTE", "ai-api: จำนวนคำขอต่อนาทีต่อคน", "int", "30", lo=1, hi=10000, group=ADVANCED),
    Setting("SYSTEM_PROMPT", "ai-api: คำสั่งระบบเริ่มต้น", "text", "You are a helpful assistant.", group=ADVANCED),
    Setting("ALLOW_CLIENT_SYSTEM", "ai-api: ให้ client ส่งคำสั่งระบบเองได้", "bool", "false", group=ADVANCED,
            note="เปิดแล้วผู้ใช้เปลี่ยนพฤติกรรม AI ได้ ไม่แนะนำถ้าเปิดให้คนอื่นใช้"),
]
BY_KEY = {s.key: s for s in SETTINGS}

_TRUE = {"1", "true", "yes", "on", "y", "ใช่", "เปิด"}
_FALSE = {"0", "false", "no", "off", "n", "ไม่", "ปิด"}


def is_secret(key: str) -> bool:
    return key in BY_KEY and BY_KEY[key].kind == "secret"


def find(key: str) -> Setting:
    """หา setting จากชื่อ (ไม่สนตัวพิมพ์) หรือแจ้งชื่อที่ใกล้เคียง"""
    name = key.strip().upper()
    if name in BY_KEY:
        return BY_KEY[name]
    near = difflib.get_close_matches(name, BY_KEY, n=3, cutoff=0.5)
    hint = f" ลองดู: {', '.join(near)}" if near else " ดูรายการทั้งหมดด้วย: python hope.py config"
    raise ValueError(f"ไม่รู้จักค่า {key}.{hint}")


def validate(key: str, raw: str, current: Callable[[str], str | None] = lambda _k: None) -> str:
    """ตรวจและแปลงค่าเป็นรูปที่เขียนลง .env ได้ ถ้าผิดจะ raise ValueError พร้อมข้อความภาษาไทย"""
    setting = find(key)
    value = raw.strip()
    if "\n" in value or "\r" in value:
        raise ValueError("ค่าต้องอยู่ในบรรทัดเดียว")
    if setting.kind == "choice":
        value = value.lower()
        if value not in setting.choices:
            raise ValueError(f"{setting.key} เลือกได้เฉพาะ: {', '.join(setting.choices)}")
    elif setting.kind == "bool":
        low = value.lower()
        if low in _TRUE:
            return "true"
        if low in _FALSE:
            return "false"
        raise ValueError(f"{setting.key} ใส่ true หรือ false")
    elif setting.kind == "int":
        try:
            number = int(value)
        except ValueError:
            raise ValueError(f"{setting.key} ต้องเป็นตัวเลขจำนวนเต็ม") from None
        if setting.lo is not None and number < setting.lo or setting.hi is not None and number > setting.hi:
            raise ValueError(f"{setting.key} ต้องอยู่ระหว่าง {setting.lo} ถึง {setting.hi}")
        if setting.key == "RAG_CHUNK_OVERLAP":
            size = int(current("RAG_CHUNK_SIZE") or BY_KEY["RAG_CHUNK_SIZE"].default)
            if number >= size:
                raise ValueError(f"ส่วนที่ซ้อนกัน ({number}) ต้องน้อยกว่าขนาดช่วง ({size})")
        if setting.key == "RAG_CHUNK_SIZE":
            overlap = int(current("RAG_CHUNK_OVERLAP") or BY_KEY["RAG_CHUNK_OVERLAP"].default)
            if number <= overlap:
                raise ValueError(f"ขนาดช่วง ({number}) ต้องมากกว่าส่วนที่ซ้อนกัน ({overlap})")
        return str(number)
    elif setting.kind == "secret":
        if not value:
            raise ValueError("ค่าว่าง ถ้าต้องการลบให้ใช้: python hope.py config unset " + setting.key)
    elif not value and setting.key not in {"ALLOWED_ORIGINS"}:
        raise ValueError(f"{setting.key} ห้ามเว้นว่าง")
    return value
