"""tool: calculator — ให้ agent คำนวณด้วย AST allowlist โดยไม่ใช้ eval()"""
import ast
import math
import operator

MAX_ABS_POWER = 10_000
MAX_EXPRESSION_LENGTH = 200

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {
    "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "abs": abs, "round": round,
}
CONSTANTS = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_ABS_POWER or abs(left) > MAX_ABS_POWER:
                raise ValueError("เลขยกกำลังใหญ่เกินกำหนด")
            return left ** right
        op = BIN_OPS.get(type(node.op))
        if op:
            return op(left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
        return UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        fn = FUNCTIONS.get(node.func.id)
        if fn:
            return fn(*[_eval(arg) for arg in node.args])
    raise ValueError("นิพจน์นี้ไม่รองรับ")


def calculate(expression: str) -> dict:
    """คำนวณนิพจน์จากรายการที่อนุญาต: + - * / // % ** และฟังก์ชันคณิตศาสตร์พื้นฐาน"""
    try:
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError("นิพจน์ยาวเกินกำหนด")
        result = _eval(ast.parse(expression, mode="eval"))
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
