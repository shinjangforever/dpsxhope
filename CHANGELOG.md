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
- เดโมหุ่นยนต์ `fields/robotics/heart-to-mechanism/simulate.py` (Python มาตรฐานล้วน): คำสั่ง > ด่านความปลอดภัย > PID > มอเตอร์ > กลไก พร้อมกราฟ SVG และชุดทดสอบ 33 ข้อ รวมชั้นป้องกันของกลไก (ตัดกำลังเมื่อตำแหน่ง ความเร็ว หรือชีพจรของตัวควบคุมผิดปกติ) และโหมด `--faults` ที่จำลองหัวใจเพ้อกับตัวควบคุมค้าง
- `robokit` (`fields/robotics/robokit/`, Python มาตรฐานล้วน) เรียกผ่าน `python hope.py robot ...`: `plan` วางแผนโปรเจกต์หุ่นยนต์เป็นขั้นที่มีเกณฑ์ผ่าน, `gate` ด่านตรวจคำสั่งจากไฟล์กฎ JSON (ช่วงค่า เขตห้ามเข้า ระยะต่อครั้ง rate limit audit log), `tune` หาค่า PID ที่ทนต่อค่าที่วัดคลาด, `stop` คำนวณระยะหยุดของชั้นป้องกัน พร้อมไฟล์กฎตัวอย่าง 3 แบบและชุดทดสอบ 32 ข้อ
- agent และ workflow ใช้ Ollama ในเครื่องได้แล้ว (`LLM_PROVIDER=ollama`) ผ่านชั้นกลาง `agent-kit/llm.py` โดยไม่ต้องติดตั้งไลบรารีเพิ่ม และ workflow ลองซ้ำได้ด้วย `retries`
- งานอัตโนมัติ `agent-kit/automate.py` เรียกผ่าน `python hope.py auto ...`: ไฟล์งาน JSON ที่เฝ้าโฟลเดอร์หรือรันตามรอบ ขั้นชนิด `tool`, `llm`, `write` พร้อม `--dry-run`, สถานะกันทำซ้ำ, ล็อกกันรันซ้อน และงานตัวอย่าง `inbox-todo` กับ `inbox-summary`
- tool ใหม่ `find_lines` และข้อเมนูไทย "งานอัตโนมัติ"
- `python hope.py stack` ตรวจภาษาและเครื่องมือในเครื่อง แล้วบอกว่าส่วนไหนของคู่มือใช้ได้แล้ว
- แผนที่ `stack/README.md` v0.2: ภาษาและเครื่องมือ, AI agent, งานอัตโนมัติ, Full stack, Cybersecurity เชิงป้องกัน, คณิตศาสตร์ และปรัชญา
- คลังข้อมูล `stack/stack.json`: เครื่องมือและภาษา 49 ชิ้นพร้อมคำอธิบาย จัดเป็น 9 กลุ่ม แยกเป็น 8 สายและ 4 ระดับ กับกลุ่มความรู้ของแต่ละสายในแต่ละระดับ หน้า `stack/TOOLS.md` และ `stack/PATHS.md` สร้างจากคลังนี้
- มุมมองใหม่ของ `python hope.py stack`: `map` (สาย × ระดับ), `tools` (กรองด้วย `--group` `--track` `--level`), `path สาย`, `show ชื่อ` และ `docs`
- ตัวอย่างในคู่มือของเครื่องมือทุกชิ้นในแผนที่ stack: `auto report` (SQLite), `auto schedule` (Task Scheduler และ cron), `auto serve` (ช่องรับไฟล์ทาง HTTP สำหรับ n8n หรือโปรแกรมอื่น), `agent-kit/mcp_server.py` (MCP แบบ stdio ตามสเปกรุ่น 2025-11-25), หน้าเว็บตัวอย่าง `stack/examples/web/` (HTML, CSS, JavaScript ล้วน ต่อกับ ai-api), `languages/cpp/stop_distance.cpp` และ `python hope.py audit` (npm audit กับ pip-audit) พร้อม workflow ตรวจประจำสัปดาห์
- บทเรียนเป็นขั้นครบทุกสายทุกระดับ (32 ช่อง) ใน `stack/lessons/` และ `python hope.py stack learn สาย` แต่ละระดับมีขั้นที่ต้องทำ สิ่งที่ควรเห็น และเกณฑ์ว่าผ่าน คำสั่งที่ไม่ต้องใช้โมเดลถูกรันโดยชุดทดสอบ
- `stack/THREAT-MODEL.md`: สิ่งที่ต้องปกป้อง เส้นแบ่งความไว้ใจ ตารางภัย 12 ข้อพร้อมสิ่งที่กันไว้และช่องว่าง ลำดับสิ่งที่ควรแก้ และแผนเมื่อเกิดเหตุ

### Changed

- audit log ของ agent ตัดข้อความใน input ที่ยาวเกิน 200 ตัวอักษร เพื่อไม่ให้เนื้อหาเอกสารทั้งไฟล์ค้างใน log
- workflow จบด้วยรหัส 1 เมื่อมีขั้นที่ล้ม และ README ของ agent-kit ไม่อ้างการรันขนานที่ไม่มีอยู่จริงแล้ว
- ตั้งชื่อโมเดลผ่าน `.env` ด้วย `CLAUDE_MODEL` และ `GEMINI_MODEL`
- ย้ายการเรียก Gemini ไปใช้ `google-genai`
- ใช้ไฟล์ `.env` เดียวที่ root ของ repo
- เปลี่ยน `agent-demo` เป็น `agent-kit` และ `workflows/examples` เป็น `workflows/templates`
- RAG ใช้ embedding หลายภาษาและ BM25 ที่รองรับข้อความไทยเป็นค่าเริ่มต้น
- ตัวแยกคำตัดวรรณยุกต์และการันต์ก่อนสร้าง n-gram **ต้องรัน `ingest` ใหม่กับ index ที่สร้างไว้ก่อนหน้า** ไม่เช่นนั้นคำที่มีเครื่องหมายเหล่านี้จะค้นไม่เจอ
- `recall@k` ใน `evaluate.py` เทียบ keyword หลังตัดวรรณยุกต์ทั้งสองข้าง
- `domains/robotics/ros2_llm_bridge.py` ส่งคำตอบของ LLM เข้าด่านตรวจของ robokit ก่อนทุกครั้ง (เดิมกรองด้วย confidence ของโมเดลอย่างเดียว) ดึง JSON อย่างปลอดภัย และมีโหมด `--offline` ที่ไม่ต้องมี key
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
