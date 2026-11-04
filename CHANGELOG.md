# Changelog

รูปแบบอ้างอิงจาก [Keep a Changelog](https://keepachangelog.com/) และใช้ [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added

- แบนเนอร์ README โทนดำทอง พร้อมภาพ social preview
- README ภาษาไทยและอังกฤษแบบคู่มือ
- MIT License สำหรับโค้ด และ CC BY 4.0 สำหรับเนื้อหา
- `CONTRIBUTING.md`, `ROADMAP.md` และ `.gitattributes`
- ตัวเลือก `LLM_PROVIDER=ollama` สำหรับตอบคำถาม RAG ในเครื่อง
- `BLUEPRINTS.md` และรายการตรวจก่อนใช้จริง
- RAG รองรับ PDF, ผลลัพธ์ JSON, ฟังก์ชัน `ask()` และชุดทดสอบจากไฟล์
- Agent มี tool registry, template, approval และ audit log
- `llm-eval` มี CLI, รายงาน JSON, เกณฑ์ขั้นต่ำ และ Ollama
- `ai-api` มี Bearer auth, CORS allowlist, ค่า host ที่ปลอดภัย และ Dockerfile
- unit tests ใน `tests/`

### Changed

- ตั้งชื่อโมเดลผ่าน `.env` ด้วย `CLAUDE_MODEL` และ `GEMINI_MODEL`
- ย้ายการเรียก Gemini ไปใช้ `google-genai`
- ใช้ไฟล์ `.env` เดียวที่ root ของ repo
- เปลี่ยน `agent-demo` เป็น `agent-kit` และ `workflows/examples` เป็น `workflows/templates`
- RAG ใช้ embedding หลายภาษาและ BM25 ที่รองรับข้อความไทยเป็นค่าเริ่มต้น

### Fixed

- Quick Start ที่ย้ายโฟลเดอร์ผิดและอ้างไฟล์ `.env.example` ที่ไม่มี
- การ import tools ใน `workflow_runner.py`
- การ import `client` ในตัวอย่าง `llm-eval`
- การจัดการ error และ API key ที่หายไปใน `ai-api`
- คำสั่งเก่าใน README ของแต่ละโมดูล

### Security

- เปลี่ยน `calculator.py` จาก `eval()` เป็น AST allowlist
- จำกัด `text_search` ไม่ให้ออกนอกโฟลเดอร์ที่เริ่มรัน
- จำกัดขนาด request และ `max_tokens` ใน `ai-api`
