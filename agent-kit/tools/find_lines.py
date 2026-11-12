"""tool: find_lines — ดึงบรรทัดที่มีคำที่กำหนดออกจากข้อความ (ไม่ใช้ AI ผลเหมือนเดิมทุกครั้ง)"""

MAX_LINES = 200


def find_lines(text: str, keywords: list[str], max_lines: int = 50) -> dict:
    """คืนบรรทัดที่มีคำใดคำหนึ่งใน keywords ไม่สนตัวพิมพ์เล็กใหญ่ พร้อมเลขบรรทัด"""
    words = [k.strip().lower() for k in keywords if isinstance(k, str) and k.strip()]
    if not words:
        return {"error": "keywords ต้องมีอย่างน้อยหนึ่งคำ"}
    limit = max(1, min(int(max_lines), MAX_LINES))
    lines = text.splitlines()
    found = []
    for number, line in enumerate(lines, 1):
        lowered = line.lower()
        if any(word in lowered for word in words):
            found.append({"line": number, "text": line.strip().lstrip("-*•").strip()})
    shown = found[:limit]
    return {
        "total_lines": len(lines),
        "found": len(found),
        "truncated": len(found) > limit,
        "lines": shown,
        "as_list": "\n".join(f"- {item['text']} (บรรทัด {item['line']})" for item in shown) or "- (ไม่พบ)",
    }


TOOL_SCHEMA = {
    "name": "find_lines",
    "description": "Return the lines of a text that contain any of the given keywords, with line numbers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to scan"},
            "keywords": {"type": "array", "items": {"type": "string"}, "description": "Words to look for"},
            "max_lines": {"type": "integer", "description": "Maximum lines to return", "default": 50},
        },
        "required": ["text", "keywords"],
    },
}
