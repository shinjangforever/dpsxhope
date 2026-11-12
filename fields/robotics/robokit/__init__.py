"""robokit: เครื่องมือหุ่นยนต์จากแผนที่สาขาหุ่นยนต์ของ dpsxhope (Python มาตรฐานล้วน)

- gate:     ด่านตรวจคำสั่งที่ตั้งกฎผ่านไฟล์ JSON วางระหว่าง AI กับตัวควบคุม
- tune:     หาค่า PID เริ่มต้นจากค่าของเครื่อง และทดสอบความทนต่อค่าที่วัดคลาด
- stopping: คำนวณระยะหยุดของชั้นป้องกัน ว่าหยุดทันก่อนชนไหม
- plan:     วางแผนโปรเจกต์จากคำตอบไม่กี่ข้อ ได้ plan.md + ไฟล์กฎตั้งต้น
"""
from .gate import Decision, Gate, ProfileError, load_profile, validate_profile

__all__ = ["Decision", "Gate", "ProfileError", "load_profile", "validate_profile"]
