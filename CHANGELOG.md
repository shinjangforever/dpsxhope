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
- `hope.py` สำหรับ `status`, `list`, `test`, `check-links` และ `check` โดยไม่ต้องใช้ API key หรือ Docker
- `catalog.json` ระบุต้นแบบแต่ละชิ้น พร้อมสิ่งที่ทดสอบแล้วและยังไม่ได้ทดสอบ
- GitHub Actions: รัน `hope.py check` และชุด mock บน Ubuntu และ Windows กับ Python 3.11 และ 3.13 (ยังไม่เคยรันบน GitHub)
- เซิร์ฟเวอร์จำลอง Anthropic ใน `tests/` และชุดทดสอบ end-to-end ของ agent, workflow, `llm-eval` และ `ai-api`
- คลังเอกสารไทย `rag-pipeline/sample_docs_th/` (8 ไฟล์) กับชุดคำถาม 30 ข้อ `eval_cases_th.json` ที่ตรวจไฟล์ต้นทางได้ด้วย `expected_source`
- ผลลัพธ์ `source top-1` และ `source top-k` ใน `pipeline.py eval` เมื่อกรณีทดสอบมี `expected_source`
- เมนูภาษาไทยผ่าน `python hope.py` (หรือดับเบิลคลิก `start.cmd` บน Windows, `bash start.sh` บน macOS และ Linux) แนะนำขั้นต่อไปตามสถานะเครื่อง
- คำสั่งใหม่ของ `hope.py`: `setup` (ติดตั้งใน `.venv`, เลือก Ollama หรือ Claude, ใส่ key แบบไม่แสดงตัวอักษร), `demo`, `docs`, `ask`, `agent`, `config`, `new-tool` และ `status` ที่บอกว่าขาดอะไร
- `pipeline.py chat` กับ `--search-only` (ค้นอย่างเดียวโดยไม่ต้องมี key)
- `hope.py check-links` ตรวจหัวข้อที่ลิงก์ชี้ไป (`#...`) และลิงก์แบบ HTML ด้วย
- ตารางเทียบ Ollama กับ Claude (ค่าใช้จ่ายและข้อมูลที่ออกจากเครื่อง) และตารางสถานการณ์ใช้งานใน README
- แผนที่สาขาแรก `fields/robotics/` v0.1: แผนที่ เส้นทางเรียน 5 ขั้น เครื่องมือ ความปลอดภัย และบทที่ 1 "จากหัวใจสู่กลไก" แหล่งอ้างอิงตรวจเมื่อ 2026-11-10
- เดโมหุ่นยนต์ `fields/robotics/heart-to-mechanism/simulate.py` (Python มาตรฐานล้วน): คำสั่ง > ด่านความปลอดภัย > PID > มอเตอร์ > กลไก พร้อมกราฟ SVG และชุดทดสอบ 21 ข้อ

### Changed

- ตั้งชื่อโมเดลผ่าน `.env` ด้วย `CLAUDE_MODEL` และ `GEMINI_MODEL`
- ย้ายการเรียก Gemini ไปใช้ `google-genai`
- ใช้ไฟล์ `.env` เดียวที่ root ของ repo
- เปลี่ยน `agent-demo` เป็น `agent-kit` และ `workflows/examples` เป็น `workflows/templates`
- RAG ใช้ embedding หลายภาษาและ BM25 ที่รองรับข้อความไทยเป็นค่าเริ่มต้น
- ตัวแยกคำตัดวรรณยุกต์และการันต์ก่อนสร้าง n-gram **ต้องรัน `ingest` ใหม่กับ index ที่สร้างไว้ก่อนหน้า** ไม่เช่นนั้นคำที่มีเครื่องหมายเหล่านี้จะค้นไม่เจอ
- `recall@k` ใน `evaluate.py` เทียบ keyword หลังตัดวรรณยุกต์ทั้งสองข้าง
- README ของ `languages/` ตรงกับไฟล์ที่มีอยู่จริง และหัวไฟล์ SQL กับ Rust บอกข้อจำกัดตามจริง

- `ingest` ข้ามไฟล์ที่ชื่อขึ้นต้นด้วย `_` หรือ `.` (ไฟล์ที่เคยชื่อแบบนี้จะไม่ถูกอ่านอีก ให้เปลี่ยนชื่อ) และ `pipeline.py` แสดงแหล่งอ้างอิงเป็นชื่อไฟล์และหัวข้อ

### Fixed

- ลิงก์ "เริ่มใน 5 นาที" ที่ด้านบนของ README ชี้ไปหัวข้อที่ไม่มีอยู่
- ข้อความจาก PDF ภาษาไทยที่วรรณยุกต์หายเป็น NUL, สระอำถูกแยก และมีช่องว่างแทรก ตอนนี้ซ่อมก่อนทำ index และแจ้งเตือนเมื่อพบการสูญเสีย
- `domains/quantum`: `grover_search` ล้มด้วย `unknown instruction: Q` และ `vqe_cost_function` เรียก Estimator เวอร์ชันเก่าผิดรูปแบบ

- Quick Start ที่ย้ายโฟลเดอร์ผิดและอ้างไฟล์ `.env.example` ที่ไม่มี
- การ import tools ใน `workflow_runner.py`
- การ import `client` ในตัวอย่าง `llm-eval`
- การจัดการ error และ API key ที่หายไปใน `ai-api`
- คำสั่งเก่าใน README ของแต่ละโมดูล

### Security

- เปลี่ยน `calculator.py` จาก `eval()` เป็น AST allowlist
- จำกัด `text_search` ไม่ให้ออกนอกโฟลเดอร์ที่เริ่มรัน
- จำกัดขนาด request และ `max_tokens` ใน `ai-api`
