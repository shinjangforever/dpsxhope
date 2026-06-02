"""tool: calculator — ให้ agent คำนวณได้โดยไม่ hallucinate ตัวเลข"""
import math


def calculate(expression: str) -> dict:
    """
    ประเมินนิพจน์คณิตศาสตร์อย่างปลอดภัย
    รองรับ: +, -, *, /, **, sqrt, log, sin, cos
    """
    allowed = {
        "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "pi": math.pi, "e": math.e, "abs": abs, "round": round,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
        return {"result": result, "expression": expression, "ok": True}
    except Exception as exc:
        return {"result": None, "expression": expression, "ok": False, "error": str(exc)}


TOOL_SCHEMA = {
    "name": "calculate",
    "description": "Evaluate a mathematical expression. Use for any arithmetic or math.",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression e.g. '2 ** 10' or 'sqrt(144)'",
            }
        },
        "required": ["expression"],
    },
}
