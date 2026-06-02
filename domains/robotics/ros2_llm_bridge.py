"""
ros2_llm_bridge.py — เชื่อม ROS 2 กับ LLM เพื่อ natural language robot control
แนวคิด: แปลง sensor data → context → ส่ง LLM → parse คำสั่ง → publish to ROS topic

ต้องการ: ROS 2 Humble/Iron + Python 3.10+
pip install anthropic

รัน (ต้องมี ROS 2 sourced):
  source /opt/ros/humble/setup.bash
  python ros2_llm_bridge.py
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


# ── Data types ────────────────────────────────────────────────

@dataclass
class RobotState:
    position: dict[str, float]     # {x, y, z}
    orientation: dict[str, float]  # {roll, pitch, yaw} radians
    battery_pct: float
    last_error: Optional[str] = None

    def to_context(self) -> str:
        return (
            f"Robot position: x={self.position['x']:.2f} y={self.position['y']:.2f} "
            f"z={self.position['z']:.2f}\n"
            f"Orientation: yaw={self.orientation['yaw']:.2f} rad\n"
            f"Battery: {self.battery_pct:.0f}%\n"
            f"Last error: {self.last_error or 'none'}"
        )


@dataclass
class RobotCommand:
    action: str          # move_to | rotate | stop | speak | wait
    params: dict
    confidence: float    # 0–1


# ── LLM command parser ────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a robot command interpreter. Given the robot's current state and a natural language
instruction, output a single JSON command object.

Available actions:
- move_to: {"action": "move_to", "params": {"x": float, "y": float, "speed": 0.1-1.0}}
- rotate:  {"action": "rotate",  "params": {"angle_deg": float, "direction": "cw|ccw"}}
- stop:    {"action": "stop",    "params": {}}
- speak:   {"action": "speak",   "params": {"text": "string"}}
- wait:    {"action": "wait",    "params": {"seconds": float}}

Reply with ONLY valid JSON. Set confidence (0-1) based on how clear the instruction is.
{"action": "...", "params": {...}, "confidence": 0.9}
"""


def parse_command(instruction: str, state: RobotState) -> RobotCommand:
    """ใช้ LLM แปลงภาษาธรรมชาติเป็น RobotCommand"""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"Robot state:\n{state.to_context()}\n\nInstruction: {instruction}"
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    data = json.loads(raw)
    return RobotCommand(
        action=data["action"],
        params=data["params"],
        confidence=float(data.get("confidence", 0.5)),
    )


# ── ROS 2 bridge (stub — ใช้จริงต้องมี rclpy) ────────────────

class LLMRobotBridge:
    """
    ใน production จะ inherit จาก rclpy.node.Node
    และ subscribe/publish ไปยัง ROS topics จริงๆ
    """

    def __init__(self, min_confidence: float = 0.7):
        self.min_confidence = min_confidence
        self.state = RobotState(
            position={"x": 0.0, "y": 0.0, "z": 0.0},
            orientation={"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            battery_pct=87.0,
        )

    def on_instruction(self, text: str) -> Optional[RobotCommand]:
        print(f"[instruction] {text}")
        cmd = parse_command(text, self.state)
        print(f"[parsed]      {cmd.action} | params={cmd.params} | conf={cmd.confidence:.2f}")

        if cmd.confidence < self.min_confidence:
            print(f"[rejected]    confidence too low ({cmd.confidence:.2f} < {self.min_confidence})")
            return None

        self._execute(cmd)
        return cmd

    def _execute(self, cmd: RobotCommand) -> None:
        # TODO: ใน production → publish ไปยัง /cmd_vel, /tts, ฯลฯ
        print(f"[execute]     publishing {cmd.action} to ROS topic")

    def update_state(self, position: dict, orientation: dict, battery: float) -> None:
        self.state.position = position
        self.state.orientation = orientation
        self.state.battery_pct = battery


# ── Demo (ไม่ต้อง ROS) ───────────────────────────────────────

if __name__ == "__main__":
    bridge = LLMRobotBridge(min_confidence=0.6)

    test_instructions = [
        "Move to coordinates 3, 4 at half speed",
        "Turn left 90 degrees",
        "Stop immediately",
        "Say hello to the user",
    ]

    for instruction in test_instructions:
        print("\n" + "─" * 50)
        bridge.on_instruction(instruction)
