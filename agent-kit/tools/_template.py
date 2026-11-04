"""คัดลอกไฟล์นี้เป็น tools/<ชื่อ tool>.py แล้วแก้ชื่อ ฟังก์ชัน และ schema"""

# ตั้งเป็น True เมื่อ tool แก้ข้อมูล จ่ายเงิน ส่งข้อความ หรือส่งข้อมูลออกนอกเครื่อง
REQUIRES_APPROVAL = False


def lookup_customer(customer_id: str) -> dict:
    """คืน dict ที่แปลงเป็น JSON ได้ อย่าคืน secret หรือข้อมูลที่ agent ไม่จำเป็นต้องเห็น"""
    return {"customer_id": customer_id, "status": "replace-with-your-system"}


TOOL_SCHEMA = {
    "name": "lookup_customer",
    "description": "Look up a customer by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"customer_id": {"type": "string", "description": "Customer ID"}},
        "required": ["customer_id"],
    },
}
