"""สร้างไฟล์ tool ใหม่ของ agent จากแม่แบบ เพื่อให้เริ่มปรับใช้ได้โดยไม่ต้องคัดลอกและแก้ชื่อเอง"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_NAME = "lookup_customer"
_NAME = re.compile(r"[a-z][a-z0-9_]{1,39}")


def existing_tools(tools_dir: Path) -> list[str]:
    return sorted(p.stem for p in Path(tools_dir).glob("*.py") if not p.name.startswith("_"))


def new_tool(name: str, tools_dir: Path | None = None) -> Path:
    """คัดลอก _template.py เป็น tools/<name>.py แล้วเปลี่ยนชื่อฟังก์ชันกับ schema ให้ตรงกัน"""
    tools_dir = Path(tools_dir or ROOT / "agent-kit" / "tools")
    if not _NAME.fullmatch(name):
        raise ValueError("ชื่อ tool ใช้ได้เฉพาะตัวพิมพ์เล็ก a-z ตัวเลข และ _ ขึ้นต้นด้วยตัวอักษร ยาว 2-40 ตัว เช่น check_stock")
    target = tools_dir / f"{name}.py"
    if target.exists():
        raise ValueError(f"มี tool ชื่อ {name} อยู่แล้วที่ {target}")
    template = tools_dir / "_template.py"
    if not template.exists():
        raise ValueError(f"ไม่พบแม่แบบ {template}")
    text = template.read_text(encoding="utf-8").replace(TEMPLATE_NAME, name)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target
