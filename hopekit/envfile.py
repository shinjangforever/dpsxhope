"""อ่านและเขียนไฟล์ .env โดยคงคอมเมนต์และลำดับเดิมไว้ ไม่พิมพ์ค่าลับออกหน้าจอ"""
import os
import re
from pathlib import Path

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_PLAIN = re.compile(r"^[^\s#'\"\\]*$")


def _unquote(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\") if value[0] == '"' else inner
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def quote(value: str) -> str:
    """ใส่เครื่องหมายคำพูดเมื่อค่ามีช่องว่าง # หรืออักขระที่ทำให้ตีความผิด"""
    if "\n" in value or "\r" in value:
        raise ValueError("ค่าต้องอยู่ในบรรทัดเดียว")
    if "${" in value:
        # python-dotenv แทนค่า ${ชื่อ} ทุกกรณี แม้อยู่ในเครื่องหมายคำพูด (ตรวจกับ dotenv จริงแล้ว) และไม่มีวิธี escape
        raise ValueError("ค่าที่มี ${ ใส่ในไฟล์ .env ไม่ได้ เพราะ python-dotenv จะแทนค่าตัวแปรให้เอง เปลี่ยนเป็นข้อความอื่น")
    if _PLAIN.match(value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _key_of(line: str) -> str | None:
    """ชื่อ key ของบรรทัดที่ตั้งค่าจริง (บรรทัดคอมเมนต์ที่ขึ้นต้นด้วย # ไม่ตรงรูปแบบนี้อยู่แล้ว)"""
    match = _LINE.match(line)
    return match.group(1) if match else None


def read(path: Path) -> dict[str, str]:
    """คืนค่าที่ตั้งไว้จริง ถ้ามี key ซ้ำให้ใช้ตัวท้ายสุดเหมือน dotenv"""
    path = Path(path)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE.match(line)
        if match:
            values[match.group(1)] = _unquote(match.group(2))
    return values


def get(path: Path, key: str, default: str | None = None) -> str | None:
    return read(path).get(key, default)


def _write(path: Path, lines: list[str]) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)  # ไฟล์นี้อาจมี API key
    except OSError:
        pass


def set_value(path: Path, key: str, value: str, template: Path | None = None) -> None:
    """ตั้งค่า key ในไฟล์ ถ้ายังไม่มีไฟล์ให้คัดลอกจาก template ก่อน (เช่น .env.example)"""
    path = Path(path)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    elif template and Path(template).exists():
        text = Path(template).read_text(encoding="utf-8")
    else:
        text = ""
    lines = text.splitlines()
    new_line = f"{key}={quote(value)}"
    kept: list[str] = []
    placed = False
    for line in lines:
        if _key_of(line) == key:
            if not placed:
                kept.append(new_line)
                placed = True
            continue  # ลบบรรทัดซ้ำของ key เดียวกัน
        kept.append(line)
    if not placed:
        if kept and kept[-1].strip():
            kept.append("")
        kept.append(new_line)
    _write(path, kept)


def unset(path: Path, key: str) -> bool:
    """ลบ key ออกจากไฟล์ คืน True ถ้ามีให้ลบ"""
    path = Path(path)
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if _key_of(line) != key]
    if len(kept) == len(lines):
        return False
    _write(path, kept)
    return True
