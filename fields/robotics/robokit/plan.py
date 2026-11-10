"""วางแผนโปรเจกต์หุ่นยนต์จากคำตอบไม่กี่ข้อ ได้แผนเป็น Markdown พร้อมไฟล์กฎด่านความปลอดภัยตั้งต้น

แผนเรียงตามชั้นในแผนที่ (หัวใจ > ด่าน > ตัวควบคุม > มอเตอร์ > กลไก > ชั้นป้องกัน) และบังคับลำดับ
simulator ก่อนฮาร์ดแวร์เสมอ แต่ละขั้นมีเกณฑ์ "ผ่านเมื่อ" ที่ตรวจได้ ไม่ใช่แค่รายการให้ติ๊ก
"""
from __future__ import annotations

import shutil
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

QUESTIONS = {
    "kind": ("หุ่นยนต์แบบไหน", {"axis": "แกนเดี่ยว / แท่นเลื่อน", "arm": "แขนกล", "mobile": "หุ่นยนต์เคลื่อนที่ (ล้อ)"}),
    "stage": ("ตอนนี้อยู่ขั้นไหน", {"idea": "มีแค่ไอเดีย", "sim": "มีแบบจำลองหรือโค้ดแล้ว", "hardware": "มีฮาร์ดแวร์แล้ว"}),
    "ai": ("ใช้ AI สั่งงานไหม", {"none": "ไม่ใช้ (สั่งด้วยโปรแกรมหรือคน)", "llm": "ใช้ LLM แปลงคำพูดเป็นคำสั่ง",
                                "vision": "ใช้โมเดลภาพหรือ VLA"}),
    "people": ("ทำงานใกล้คนไหม", {"no": "ไม่ (มีรั้วกั้นหรือใช้คนเดียวบนโต๊ะ)", "yes": "ใช่ คนเข้าถึงพื้นที่ทำงานได้"}),
    "use": ("ใช้ทำอะไร", {"learn": "เรียน / งานอดิเรก", "prototype": "ต้นแบบสินค้า", "work": "ใช้งานจริง / ในโรงงาน"}),
}
PROFILE_FOR = {"axis": "rail-1axis.json", "arm": "desk-arm-2axis.json", "mobile": "mobile-base.json"}


def check_answers(answers: dict) -> None:
    for key, (_, options) in QUESTIONS.items():
        if answers.get(key) not in options:
            raise ValueError(f"{key} ต้องเป็นหนึ่งใน {sorted(options)}")


def build_plan(answers: dict, name: str = "หุ่นยนต์ของฉัน") -> str:
    check_answers(answers)
    a = answers
    label = {k: QUESTIONS[k][1][a[k]] for k in QUESTIONS}
    near_people = a["people"] == "yes"
    high_stakes = near_people or a["use"] == "work"
    sim_tool = {"axis": "แบบจำลองของ robokit (tune) แล้วต่อด้วย MuJoCo ถ้าต้องการการสัมผัส",
                "arm": "MuJoCo (Apache-2.0) สำหรับแขนกลและการสัมผัส",
                "mobile": "Gazebo (Apache-2.0) คู่กับ ROS 2"}[a["kind"]]
    out = [f"# แผนโปรเจกต์: {name}", "",
           "> สร้างด้วย `robokit plan` จาก dpsxhope · เป็นแผนตั้งต้น ไม่ใช่คำรับรองด้านความปลอดภัย", "",
           "## สรุป", ""]
    out += [f"- {QUESTIONS[k][0]}: **{label[k]}**" for k in QUESTIONS]
    out += ["", "## ขั้นตอน (ห้ามข้ามขั้น simulator)", "",
            "| ขั้น | ทำอะไร | ผ่านเมื่อ |", "|---|---|---|"]
    steps = [
        ("0. ขอบเขต", "เขียนว่าหุ่นยนต์ต้องทำอะไร ห้ามทำอะไร พื้นที่ทำงานกี่เมตร/องศา ความเร็วสูงสุดเท่าไร",
         "มีไฟล์กฎด่านความปลอดภัย (`safety-profile.json`) ที่ `robokit gate validate` ผ่าน"),
        ("1. ตัวควบคุม", "ใส่มวล แรงเสียดทาน และแรงมอเตอร์ (ประมาณก่อน) แล้วรัน `robokit tune`",
         "ได้ค่า PID ที่เกินเป้าไม่เกินสเปกแม้ค่าคลาด ±30%"),
        ("2. ชั้นป้องกัน", "รัน `robokit stop` ด้วยความเร็วสูงสุด เวลาตอบสนอง และอัตราเบรก",
         "ระยะหยุดรวม x1.5 ไม่เกินระยะจากขอบพื้นที่ถึงจุดชน"),
        ("3. จำลองเต็มระบบ", f"ใช้ {sim_tool} ส่งคำสั่งทุกคำสั่งผ่าน `Gate` ก่อนถึงตัวควบคุม",
         "รันชุดคำสั่งทดสอบ (รวมคำสั่งอันตราย) แล้วด่านปฏิเสธครบ บันทึก audit log ได้"),
    ]
    if a["ai"] != "none":
        steps.append(("4. ต่อ AI", "ให้ AI คืน JSON ตามรูปแบบในไฟล์กฎ แล้วส่งเข้า `Gate.check()` เท่านั้น",
                      "ทดสอบคำสั่งชวนหลง (prompt injection) และคำสั่งกำกวมอย่างน้อย 20 แบบ ด่านปฏิเสธหรือขอถามซ้ำทุกครั้ง"))
    steps.append(("5. ฮาร์ดแวร์บนโต๊ะ" if a["kind"] != "mobile" else "5. ฮาร์ดแวร์ยกล้อลอย",
                  "ต่อฮาร์ดแวร์ที่แรงต่ำและความเร็วจำกัดก่อน ปุ่มหยุดฉุกเฉินตัดไฟที่ฮาร์ดแวร์",
                  "วัดระยะหยุดจริงแล้วใส่ค่าจริงใน `robokit stop` ยังผ่าน และวัดมวล/แรงเสียดทานจริงแล้วจูนใหม่"))
    steps.append(("6. ใช้งาน", "ขยายความเร็วและพื้นที่ทีละขั้น เก็บ log ทุกครั้ง",
                  "ผ่านการประเมินความเสี่ยงโดยผู้มีประสบการณ์" if high_stakes else "ใช้ซ้ำได้โดยไม่มีเหตุการณ์ผิดปกติใน log"))
    out += [f"| {s} | {w} | {d} |" for s, w, d in steps]
    out += ["", "## ตรวจรายชั้น", ""]
    layers = [
        ("หัวใจ", ["คืน JSON รูปแบบเดียวเท่านั้น ไม่ส่งข้อความอิสระไปถึงตัวควบคุม",
                   "คำสั่งกำกวมให้ถามกลับ ไม่เดา"] if a["ai"] != "none" else ["คำสั่งทุกแหล่ง (ปุ่ม สคริปต์ เครือข่าย) ผ่านด่านเดียวกัน"]),
        ("ด่านความปลอดภัย", ["ทุกตัวเลขมี min/max", "มีเขตห้ามเข้า (keep_out) สำหรับจุดที่ชนแล้วเสียหาย",
                             "มี max_step จำกัดระยะต่อคำสั่ง", "คำสั่ง stop ผ่านได้เสมอ"]),
        ("ตัวควบคุม", ["มี anti-windup", "ส่งชีพจร (heartbeat) ให้ชั้นป้องกันทุกรอบ"]),
        ("มอเตอร์", ["จำกัดกระแส/แรงที่ตัวขับ ไม่ใช่แค่ในโค้ด", "รู้ค่าคงที่แรงบิดเพื่อแปลงค่า PID"]),
        ("กลไก", ["มีปลายทางกายภาพ (hard stop) หรือสวิตช์สุดทาง", "รู้ระยะจากขอบพื้นที่ถึงจุดชน"]),
        ("ชั้นป้องกันของกลไก", ["แยกจากคอมพิวเตอร์ที่รันหัวใจและตัวควบคุม", "ตัดกำลังเมื่อตำแหน่ง ความเร็ว หรือชีพจรผิดปกติ",
                                "ปุ่มหยุดฉุกเฉินตัดไฟที่ฮาร์ดแวร์"]),
    ]
    for layer, items in layers:
        out.append(f"**{layer}**")
        out += [f"- [ ] {item}" for item in items]
        out.append("")
    out += ["## ความเสี่ยงที่ต้องรู้", ""]
    risks = []
    if a["ai"] != "none":
        risks.append("LLM ที่คุมหุ่นยนต์ถูกหลอกให้ทำสิ่งอันตรายได้ (Robey และคณะ 2024, arXiv 2410.13691) ด่านกฎตายตัวจึงห้ามขาด")
    if a["ai"] == "vision":
        risks.append("โมเดลภาพพลาดได้ในแสงหรือมุมที่ไม่เคยเห็น ทดสอบในสภาพแวดล้อมจริงหลายช่วงเวลา")
    if near_people:
        risks.append("ทำงานใกล้คน: ด่านซอฟต์แวร์ไม่พอ ต้องมีอุปกรณ์ความปลอดภัยที่ผ่านการรับรองและการประเมินความเสี่ยงตามมาตรฐาน")
    if a["use"] == "work":
        risks.append("ใช้งานจริงในโรงงาน: ตรวจ ISO 10218-1/-2:2025 กับ ISO โดยตรง และให้ผู้ผสานระบบที่มีประสบการณ์ประเมิน")
    if a["kind"] == "mobile":
        risks.append("หุ่นยนต์เคลื่อนที่: ระยะหยุดเปลี่ยนตามพื้นและน้ำหนักบรรทุก วัดซ้ำทุกพื้นที่ใช้งาน")
    risks.append("เอกสารนี้ไม่ใช่คำแนะนำด้านวิศวกรรมความปลอดภัยหรือกฎหมาย")
    out += [f"- {r}" for r in risks]
    out += ["", "## คำสั่งที่ใช้ต่อ", "", "```bash",
            "python hope.py robot gate validate safety-profile.json",
            "python hope.py robot tune --mass 1.0 --friction 0.8 --max-force 20 --step 0.2",
            "python hope.py robot stop --speed 0.5 --react 0.05 --decel 5 --available 0.1",
            "```", ""]
    return "\n".join(out)


def write_plan(answers: dict, out_dir, name: str = "หุ่นยนต์ของฉัน") -> list:
    """เขียน plan.md และ safety-profile.json (ไม่เขียนทับไฟล์กฎที่มีอยู่แล้ว เพราะอาจแก้ไว้แล้ว)"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.md"
    plan_path.write_text(build_plan(answers, name), encoding="utf-8", newline="\n")
    written = [plan_path]
    profile_path = out_dir / "safety-profile.json"
    if not profile_path.exists():
        shutil.copyfile(PROFILES_DIR / PROFILE_FOR[answers["kind"]], profile_path)
        written.append(profile_path)
    return written
