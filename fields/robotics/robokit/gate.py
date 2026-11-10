"""ด่านตรวจคำสั่งหุ่นยนต์ที่ตั้งกฎผ่านไฟล์ (safety profile)

วางไว้ระหว่าง "หัวใจ" (LLM, VLA หรือคน) กับตัวควบคุม ทุกคำสั่งต้องผ่านตรงนี้ก่อน
หลักการเดียวกับเดโมบทที่ 1 แต่ใช้กับหุ่นยนต์ของคุณเองได้โดยแก้แค่ไฟล์ JSON:

- ปฏิเสธ ไม่ใช่ปรับค่าให้เงียบๆ (การ clamp ทำให้ผู้สั่งคิดว่าหุ่นยนต์ทำตามที่สั่ง)
- เข้มงวดเป็นค่าเริ่มต้น: action หรือฟิลด์ที่ไม่รู้จักทำให้ทั้งคำสั่งถูกปฏิเสธ
- ไม่พึ่งค่าความมั่นใจที่โมเดลรายงานเอง
- ไม่รู้ข้อมูลที่ต้องใช้ตรวจ (เช่น ตำแหน่งปัจจุบัน) = ปฏิเสธ (fail closed)
- คำสั่งหยุดผ่านได้เสมอ ไม่ติด rate limit

ข้อจำกัด: ด่านนี้เป็นซอฟต์แวร์ ตรวจได้เฉพาะสิ่งที่เขียนเป็นกฎได้ ไม่รู้ว่ามีคนยืนอยู่ตรงเป้าหมายหรือไม่
หุ่นยนต์จริงต้องมีชั้นป้องกันที่เป็นฮาร์ดแวร์แยกอีกชั้น (ปุ่มหยุดฉุกเฉิน สวิตช์สุดทาง ตัวจำกัดแรง)
"""
from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

TYPES = {"number", "integer", "string", "enum", "boolean"}
TOP_KEYS = {"name", "description", "units", "actions", "keep_out", "ignore_fields", "always_allow",
            "rate_limit_per_s"}
ACTION_KEYS = {"params", "required", "max_step", "description"}


class ProfileError(ValueError):
    """ไฟล์กฎผิดรูปแบบ ไม่ยอมโหลด เพราะด่านที่ตั้งผิดอันตรายกว่าไม่มีด่าน (ทำให้คนวางใจผิดๆ)"""


@dataclass
class Decision:
    ok: bool
    command: dict | None = None            # คำสั่งที่ผ่านแล้ว (ตัวเลขเป็น float, เติมค่า default)
    reasons: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_param_spec(where: str, p, required: bool) -> list:
    if not isinstance(p, dict) or p.get("type") not in TYPES:
        return [f"{where}: ต้องระบุ type เป็นหนึ่งใน {sorted(TYPES)}"]
    problems = []
    kind = p["type"]
    if kind in ("number", "integer"):
        lo, hi = p.get("min"), p.get("max")
        if lo is None or hi is None:
            problems.append(f"{where}: ตัวเลขต้องมีทั้ง min และ max (ไม่มีขอบเขต = ไม่มีด่าน)")
        elif not (_is_number(lo) and _is_number(hi)) or lo > hi:
            problems.append(f"{where}: min และ max ต้องเป็นตัวเลข และ min ต้องไม่เกิน max")
    elif kind == "enum" and (not isinstance(p.get("values"), list) or not p["values"]):
        problems.append(f"{where}: enum ต้องมี values อย่างน้อย 1 ค่า")
    elif kind == "string" and not (isinstance(p.get("max_length"), int) and p["max_length"] > 0):
        problems.append(f"{where}: string ต้องมี max_length เป็นจำนวนเต็มบวก")
    if "default" in p:
        if required:
            problems.append(f"{where}: ฟิลด์ที่บังคับใส่ไม่ควรมี default")
        elif not problems and _check_value(where, p["default"], p)[1]:
            problems.append(f"{where}: ค่า default ไม่ผ่านกฎของตัวเอง")
    return problems


def validate_profile(profile) -> list:
    """ตรวจไฟล์กฎ คืนรายการปัญหา (ว่าง = ใช้ได้)"""
    if not isinstance(profile, dict):
        return ["ไฟล์กฎต้องเป็น JSON object"]
    actions = profile.get("actions")
    if not isinstance(actions, dict) or not actions:
        return ['ต้องมี "actions" อย่างน้อย 1 รายการ']
    problems = [f"ไม่รู้จักหัวข้อ {key!r} (สะกดผิดหรือเปล่า) หัวข้อที่รู้จัก: {sorted(TOP_KEYS)}"
                for key in sorted(set(profile) - TOP_KEYS)]
    numeric_params = set()
    for name, spec in actions.items():
        if not isinstance(spec, dict):
            problems.append(f"actions.{name} ต้องเป็น object (ใช้ {{}} ถ้าไม่มีพารามิเตอร์)")
            continue
        problems += [f"actions.{name}: ไม่รู้จักหัวข้อ {key!r}" for key in sorted(set(spec) - ACTION_KEYS)]
        params = spec.get("params", {})
        required = spec.get("required", [])
        if not isinstance(params, dict) or not isinstance(required, list):
            problems.append(f"actions.{name}: params ต้องเป็น object และ required ต้องเป็นรายการ")
            continue
        for pname, p in params.items():
            problems += _check_param_spec(f"actions.{name}.params.{pname}", p, pname in required)
            if isinstance(p, dict) and p.get("type") in ("number", "integer"):
                numeric_params.add(pname)
        problems += [f"actions.{name}.required มี {req!r} ที่ไม่อยู่ใน params" for req in required if req not in params]
        for key, step in (spec.get("max_step") or {}).items():
            if not isinstance(params.get(key), dict) or params[key].get("type") not in ("number", "integer"):
                problems.append(f"actions.{name}.max_step.{key}: ต้องเป็นพารามิเตอร์ตัวเลขของ action นี้")
            elif not _is_number(step) or step <= 0:
                problems.append(f"actions.{name}.max_step.{key}: ต้องเป็นตัวเลขบวก")
    for i, zone in enumerate(profile.get("keep_out", [])):
        axes = {k: v for k, v in zone.items() if k != "name"} if isinstance(zone, dict) else {}
        if not axes:
            problems.append(f'keep_out[{i}] ต้องเป็น object ที่มีอย่างน้อย 1 แกน เช่น "x": [0.2, 0.3]')
        for axis, rng in axes.items():
            if axis not in numeric_params:
                problems.append(f"keep_out[{i}].{axis}: ไม่มีพารามิเตอร์ตัวเลขชื่อนี้ใน action ใดเลย")
            elif not (isinstance(rng, list) and len(rng) == 2 and all(map(_is_number, rng)) and rng[0] < rng[1]):
                problems.append(f"keep_out[{i}].{axis}: ต้องเป็น [ต่ำ, สูง] โดยต่ำ < สูง")
    problems += [f"always_allow มี {name!r} ที่ไม่อยู่ใน actions"
                 for name in profile.get("always_allow", []) if name not in actions]
    rate = profile.get("rate_limit_per_s")
    if rate is not None and (not _is_number(rate) or rate <= 0):
        problems.append("rate_limit_per_s ต้องเป็นตัวเลขบวก")
    if not isinstance(profile.get("ignore_fields", []), list):
        problems.append("ignore_fields ต้องเป็นรายการชื่อฟิลด์")
    return problems


def _raise_if_invalid(profile, source="") -> dict:
    problems = validate_profile(profile)
    if problems:
        raise ProfileError(f"ไฟล์กฎ{source}มีปัญหา:\n  - " + "\n  - ".join(problems))
    return profile


def load_profile(path) -> dict:
    try:
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProfileError(f"ไม่พบไฟล์กฎ {path}") from None
    except json.JSONDecodeError as exc:
        raise ProfileError(f"ไฟล์กฎ {path} ไม่ใช่ JSON ที่ถูกต้อง: {exc}") from None
    return _raise_if_invalid(profile, f" {path} ")


class Gate:
    """ด่านตรวจคำสั่ง ใช้แบบ: decision = gate.check(command, state); if decision: ส่งต่อ decision.command

    state = ค่าปัจจุบันที่วัดได้จริง เช่น {"x": 0.1, "y": 0.2} ใช้ตรวจ max_step
    """

    def __init__(self, profile: dict, log_path=None, clock=time.monotonic):
        self.profile = _raise_if_invalid(profile, " ")
        self.log_path = Path(log_path) if log_path else None
        self.clock = clock
        self._accepted = deque()            # เวลาของคำสั่งที่ผ่านในวินาทีล่าสุด (สำหรับ rate limit)

    @classmethod
    def from_file(cls, path, **kwargs) -> "Gate":
        return cls(load_profile(path), **kwargs)

    def check(self, command, state: dict | None = None) -> Decision:
        decision = self._check(command, state or {})
        if decision.ok and decision.command["action"] not in self.profile.get("always_allow", []):
            self._accepted.append(self.clock())
        self._log(command, decision)
        return decision

    def _check(self, command, state: dict) -> Decision:
        if isinstance(command, str):
            try:
                command = json.loads(command)
            except json.JSONDecodeError:
                return Decision(False, reasons=["ไม่ใช่ JSON (ด่านไม่เดาความหมายจากข้อความ)"])
        if not isinstance(command, dict):
            return Decision(False, reasons=["คำสั่งต้องเป็น JSON object"])
        actions = self.profile["actions"]
        action = command.get("action")
        if not isinstance(action, str) or action not in actions:
            return Decision(False, reasons=[f"ไม่อนุญาต action {action!r} (อนุญาตเฉพาะ {sorted(actions)})"])
        reasons = []
        extra = set(command) - {"action", "params"} - set(self.profile.get("ignore_fields", []))
        if extra:
            reasons.append(f"พบฟิลด์ที่ไม่รู้จัก {sorted(extra)} จึงปฏิเสธทั้งคำสั่ง")
        spec = actions[action]
        pspec = spec.get("params", {})
        params = command.get("params", {})
        if not isinstance(params, dict):
            return Decision(False, reasons=reasons + ["params ต้องเป็น object"])
        reasons += [f"ไม่รู้จักพารามิเตอร์ {key!r} ของ {action}" for key in sorted(set(params) - set(pspec))]
        clean = {}
        for key, p in pspec.items():
            if key not in params:
                if key in spec.get("required", []):
                    reasons.append(f"ขาด {key!r} ซึ่งต้องใส่")
                elif "default" in p:
                    clean[key] = p["default"]
                continue
            value, problem = _check_value(key, params[key], p)
            if problem:
                reasons.append(problem)
            else:
                clean[key] = value
        if not reasons:
            reasons = self._check_motion(spec, clean, state)
        if not reasons and action not in self.profile.get("always_allow", []):
            reasons = self._check_rate()
        if reasons:
            return Decision(False, reasons=reasons)
        return Decision(True, {"action": action, "params": clean})

    def _check_motion(self, spec, clean, state) -> list:
        reasons = []
        for zone in self.profile.get("keep_out", []):
            axes = {k: v for k, v in zone.items() if k != "name"}
            if all(k in clean for k in axes) and all(lo <= clean[k] <= hi for k, (lo, hi) in axes.items()):
                reasons.append(f"เป้าหมายอยู่ในเขตห้ามเข้า {zone.get('name', '(ไม่มีชื่อ)')!r}")
        for key, step in (spec.get("max_step") or {}).items():
            if key not in clean:
                continue
            current = state.get(key)
            if not _is_number(current):
                reasons.append(f"ไม่รู้ค่าปัจจุบันของ {key!r} จึงตรวจระยะต่อครั้งไม่ได้ (ปฏิเสธไว้ก่อน)")
            elif abs(clean[key] - current) > step:
                reasons.append(f"{key} เปลี่ยนจาก {current:g} เป็น {clean[key]:g} เกินที่อนุญาตต่อครั้ง {step:g}")
        return reasons

    def _check_rate(self) -> list:
        rate = self.profile.get("rate_limit_per_s")
        if not rate:
            return []
        now = self.clock()
        while self._accepted and now - self._accepted[0] >= 1.0:
            self._accepted.popleft()
        return [f"ส่งคำสั่งถี่เกิน {rate:g} ครั้งต่อวินาที"] if len(self._accepted) >= rate else []

    def _log(self, command, decision: Decision) -> None:
        if not self.log_path:
            return
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "ok": decision.ok, "input": command,
                 "command": decision.command, "reasons": decision.reasons}
        try:
            line = json.dumps(entry, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):             # เช่น input มี NaN: เก็บเป็นข้อความแทน ไม่ให้ log พัง
            entry["input"] = repr(command)
            line = json.dumps(entry, ensure_ascii=False)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _check_value(key, value, p):
    """คืน (ค่าที่ผ่านแล้ว, None) หรือ (None, เหตุผลที่ปฏิเสธ)"""
    kind = p["type"]
    if kind in ("number", "integer"):
        if not _is_number(value):
            return None, f"{key} ต้องเป็นตัวเลขที่จำกัดค่า (ไม่ใช่ข้อความ NaN หรือ infinity) ได้ {value!r}"
        if kind == "integer" and value != int(value):
            return None, f"{key} ต้องเป็นจำนวนเต็ม ได้ {value!r}"
        if not p["min"] <= value <= p["max"]:
            unit = f" {p['unit']}" if p.get("unit") else ""
            return None, f"{key} = {value:g}{unit} อยู่นอกช่วงที่อนุญาต {p['min']:g} ถึง {p['max']:g}{unit}"
        return (int(value) if kind == "integer" else float(value)), None
    if kind == "boolean":
        return (value, None) if isinstance(value, bool) else (None, f"{key} ต้องเป็น true หรือ false")
    if kind == "enum":
        return (value, None) if value in p["values"] else (None, f"{key} ต้องเป็นหนึ่งใน {p['values']} ได้ {value!r}")
    if not isinstance(value, str):
        return None, f"{key} ต้องเป็นข้อความ"
    if len(value) > p["max_length"]:
        return None, f"{key} ยาว {len(value)} ตัวอักษร เกินที่อนุญาต {p['max_length']}"
    return value, None
