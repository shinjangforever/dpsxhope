# Server maintenance

Production servers are patched every first Sunday of the month after a verified backup.

# การ deploy

ทีมต้อง deploy ระบบในช่วงหลังเที่ยงคืนถึงตีสี่เท่านั้น และห้าม deploy ในวันศุกร์ เว้นแต่เป็นการแก้ไขเร่งด่วนที่ได้รับอนุมัติ

# Rollback

หากอัตราข้อผิดพลาดเกินห้าเปอร์เซ็นต์ภายในสิบนาทีหลัง deploy ให้ rollback ทันทีโดยไม่ต้องรออนุมัติ
