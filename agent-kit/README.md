# agent-kit

ต้นแบบ agent ด้วย Claude tool use สำหรับเรียกระบบภายใน พร้อม tool registry, approval และ audit log

## สถาปัตยกรรม

```
agent.py           — ReAct loop หลัก (Reason → Tool call → Observation → ...)
tools/             — tool definitions (function specs + handlers)
workflows/         — multi-step workflow runners
```

## Features

- **ReAct loop** — agent วางแผน เรียก tool รับ observation วนซ้ำจนได้คำตอบ
- **Tool use** — Claude `tool_use` API มาตรฐาน
- **Workflow runner** — orchestrate งานหลายขั้นตอนแบบ sequential / parallel
- **Error recovery** — retry และ fallback เมื่อ tool พัง

## เริ่มใช้งาน

```bash
pip install -r requirements.txt
cp ../.env.example ../.env   # ใส่ ANTHROPIC_API_KEY
python agent.py "What is sqrt(65536)?"
python workflows/workflow_runner.py workflows/templates/research_workflow.json "What is RAG?"
```

## นำไปใช้จริง

1. คัดลอก [`tools/_template.py`](tools/_template.py) เป็น `tools/<ชื่อ tool>.py`
2. เปลี่ยน schema และฟังก์ชันให้เรียกระบบของคุณ
3. ตั้ง `REQUIRES_APPROVAL = True` สำหรับ tool ที่แก้ข้อมูลหรือส่งข้อมูลออก
4. จำกัด tool ด้วย `--tools` และกำหนด prompt ด้วย `--system-file`

```bash
python agent.py --tools lookup_customer --system-file my_system.md "ตรวจสถานะลูกค้า A001"
```

audit log อยู่ที่ `logs/audit.jsonl` เปลี่ยนตำแหน่งได้ด้วย `AGENT_AUDIT_LOG` และ input ของ tool จะถูกบันทึก จึงไม่ควรส่ง secret ผ่าน tool

**ไม่เหมาะเมื่อ:** งานต้องรันนานหลายชั่วโมง ต้องกู้สถานะอัตโนมัติ หรือต้องควบคุมสิทธิ์ผู้ใช้หลายคนโดยยังไม่มีระบบ auth

## เทคโนโลยี

Python · Anthropic Claude · Tool Use API
