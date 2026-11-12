<!-- ไฟล์นี้สร้างจาก stack/stack.json และ stack/lessons.json ด้วย python hope.py stack docs อย่าแก้ตรงนี้ -->

# สายและระดับ

8 สาย แต่ละสายมี 4 ระดับ แต่ละช่องบอกความรู้ที่ควรมี สิ่งที่ทำได้เมื่อจบ เครื่องมือที่เริ่มใช้ และเนื้อหาในคู่มือนี้ คำอธิบายของเครื่องมืออยู่ที่ [TOOLS.md](TOOLS.md)

| ระดับ | ชื่อ | ความหมาย |
|---|---|---|
| 1 | เริ่มใช้ | ใช้ของที่มีให้ได้ผล โดยยังไม่ต้องเขียนโค้ด |
| 2 | ปรับใช้ | แก้ค่า เขียนส่วนเล็ก และต่อยอดต้นแบบให้เข้ากับงานของตัวเอง |
| 3 | สร้างระบบ | ทำให้คนอื่นใช้ได้ รันได้ต่อเนื่อง และดูแลต่อได้ |
| 4 | เชี่ยวชาญ | ออกแบบ วัดผล และตัดสินใจเชิงระบบด้วยหลักฐาน |

ไม่จำเป็นต้องไปถึงระดับ 4 ทุกสาย เลือกสายตามเป้าหมาย แล้วไปให้ลึกเท่าที่งานต้องการ

## AI agent

คำถามของสายนี้: โมเดลลงมือทำอะไรได้บ้าง และใครอนุมัติ

บทเรียนเป็นขั้นของสายนี้: [lessons/agent.md](lessons/agent.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | agent ต่างจากแชตอย่างไร · tool คืออะไร · เลือกโมเดลในเครื่องหรือบนคลาวด์ | สั่ง agent ให้ใช้ tool ที่มีอยู่ และอ่านได้ว่ามันทำอะไรไป | agent-kit, Claude API, hope.py, JSON และ YAML, Ollama, Python | [`agent-kit/README.md`](../agent-kit/README.md) |
| 2 ปรับใช้ | เขียน tool และ schema · system prompt · จำกัด tool ต่องาน · การขออนุมัติ | เพิ่ม tool ของตัวเอง และจำกัดสิ่งที่ agent ทำได้ | audit log, llm-eval, workflow runner, การขออนุมัติ tool | [`agent-kit/tools/_template.py`](../agent-kit/tools/_template.py), [`agent-kit/agent.py`](../agent-kit/agent.py) |
| 3 สร้างระบบ | workflow หลายขั้น · ลองซ้ำเมื่อล้ม · audit log · ชั้นกลางที่เปลี่ยนโมเดลได้ | ต่อ agent เข้ากับระบบจริง โดยตรวจย้อนหลังได้ว่าเกิดอะไร | llama.cpp, Model Context Protocol (MCP), TypeScript | [`agent-kit/workflows/workflow_runner.py`](../agent-kit/workflows/workflow_runner.py), [`agent-kit/llm.py`](../agent-kit/llm.py), [`BLUEPRINTS.md`](../BLUEPRINTS.md) |
| 4 เชี่ยวชาญ | วัดคุณภาพการเลือก tool · prompt injection · งานยาวและการกู้สถานะ · หลาย agent ทำงานร่วมกัน | ตัดสินได้ด้วยตัวเลขว่า agent พร้อมใช้งานจริงหรือยัง | - | [`llm-eval/README.md`](../llm-eval/README.md) |

## งานอัตโนมัติ

คำถามของสายนี้: งานนี้เริ่มเองได้ไหม โดยไม่ต้องมีคนสั่งทุกครั้ง

บทเรียนเป็นขั้นของสายนี้: [lessons/automation.md](lessons/automation.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | งานแบบไหนควรทำอัตโนมัติ · ดูก่อนทำ (dry run) · โฟลเดอร์เข้าและโฟลเดอร์ออก | รันงานตัวอย่างกับไฟล์ของตัวเอง และรู้ว่าผลอยู่ที่ไหน | Git, hope.py, JSON และ YAML, Ollama, Python, งานอัตโนมัติ (automate.py) | [`agent-kit/jobs/inbox-todo.json`](../agent-kit/jobs/inbox-todo.json), [`agent-kit/README.md`](../agent-kit/README.md) |
| 2 ปรับใช้ | เขียนไฟล์งานเอง · ตัวแปรและผลของขั้นก่อนหน้า · ทำซ้ำแล้วผลไม่ซ้อน · ตั้งเวลา | สร้างงานของตัวเองที่รันซ้ำได้โดยผลไม่เพี้ยน | audit log, Bash, JavaScript, n8n, SQLite, Task Scheduler และ cron, unittest, workflow runner | [`agent-kit/jobs/inbox-summary.json`](../agent-kit/jobs/inbox-summary.json), [`agent-kit/automate.py`](../agent-kit/automate.py) |
| 3 สร้างระบบ | ล้มแล้วรู้และลองใหม่ · ล็อกกันรันซ้อน · log ที่ไม่เก็บข้อมูลลับ · ทดสอบอัตโนมัติเมื่อ push | ปล่อยงานให้รันเองได้โดยรู้เมื่อมันพัง | Docker, GitHub Actions | [`tests/test_automation.py`](../tests/test_automation.py), [`.github/workflows`](../.github/workflows) |
| 4 เชี่ยวชาญ | วัดเวลาที่ประหยัดได้จริง · ถามสถิติจาก log ด้วย SQL · รับงานจากบริการอื่นทาง HTTP · คิวงานและการกู้กลางขั้น (ยังไม่มีในคู่มือ) | ตัดสินด้วยตัวเลขว่างานอัตโนมัติคุ้มที่จะดูแลต่อไหม และรู้ว่าเมื่อไรงานเกินขอบเขตของเครื่องมือนี้ | - | [`agent-kit/autotools.py`](../agent-kit/autotools.py), [`stack/THREAT-MODEL.md`](../stack/THREAT-MODEL.md) |

## ข้อมูลและการค้นหา

คำถามของสายนี้: คำตอบมาจากข้อมูลไหน และดีแค่ไหน

บทเรียนเป็นขั้นของสายนี้: [lessons/data.md](lessons/data.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | ถามตอบจากเอกสารทำงานอย่างไร · แหล่งอ้างอิงของคำตอบ · ไฟล์แบบไหนอ่านได้ | ใส่เอกสารของตัวเอง ถามคำถาม และตรวจคำตอบกับแหล่งอ้างอิง | Claude API, hope.py, Ollama, pypdf, Python | [`rag-pipeline/README.md`](../rag-pipeline/README.md) |
| 2 ปรับใช้ | การตัดเอกสารเป็นช่วง · ค้นด้วยคำและค้นด้วยความหมาย · จำนวนช่วงที่ส่งให้โมเดล | ปรับการค้นให้เข้ากับเอกสารของตัวเอง | BM25 (rank-bm25), FAISS, Gemini API, llm-eval, NumPy, sentence-transformers, SQL, SQLite | [`rag-pipeline/chunking.py`](../rag-pipeline/chunking.py), [`rag-pipeline/retrieve.py`](../rag-pipeline/retrieve.py) |
| 3 สร้างระบบ | ชุดคำถามทดสอบของตัวเอง · เกณฑ์ผ่านใน CI · เก็บ log การเรียกโมเดล | รู้ทุกครั้งที่แก้ว่าคุณภาพการค้นและคำตอบดีขึ้นหรือแย่ลง | llama.cpp, PostgreSQL | [`rag-pipeline/eval_cases_th.json`](../rag-pipeline/eval_cases_th.json), [`llm-eval/README.md`](../llm-eval/README.md), [`languages/sql/ai_logs_schema.sql`](../languages/sql/ai_logs_schema.sql) |
| 4 เชี่ยวชาญ | เลือกและเทียบ embedding · จัดอันดับซ้ำ · ภาษาไทยและการตัดคำ · ข้อมูลส่วนบุคคล | ออกแบบระบบค้นหาสำหรับเอกสารจำนวนมากด้วยผลวัดจริง | Rust | [`rag-pipeline/textutil.py`](../rag-pipeline/textutil.py) |

## Full stack

คำถามของสายนี้: คนอื่นจะใช้งานนี้ผ่านอะไร

บทเรียนเป็นขั้นของสายนี้: [lessons/fullstack.md](lessons/fullstack.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | หน้าจอ บริการ ข้อมูล คืออะไร · terminal และเมนู · ไฟล์ตั้งค่า | อธิบายได้ว่างานชิ้นหนึ่งประกอบด้วยส่วนไหนบ้าง | Claude API, Git, JSON และ YAML, Python, ไฟล์ .env | [`stack/README.md`](../stack/README.md) |
| 2 ปรับใช้ | HTTP และ API · JSON · เรียกบริการจากโปรแกรม · Git | เรียก API ที่มีอยู่จากโค้ดของตัวเอง | HTML และ CSS, JavaScript, Node.js, SQL, SQLite, unittest | [`ai-api/README.md`](../ai-api/README.md), [`languages/typescript/client.ts`](../languages/typescript/client.ts) |
| 3 สร้างระบบ | ตรวจสิทธิ์และจำกัดอัตรา · ตรวจ input · ห่อด้วย Docker · หลายบริการรันด้วยกัน | เปิดงาน AI เป็นบริการที่คนอื่นเรียกได้อย่างปลอดภัย | Docker, Docker Compose, Express, GitHub Actions, Go, npm audit, PostgreSQL, Redis, TypeScript | [`ai-api/index.js`](../ai-api/index.js), [`ai-api/Dockerfile`](../ai-api/Dockerfile), [`languages/yaml/ai_stack.docker-compose.yml`](../languages/yaml/ai_stack.docker-compose.yml), [`BLUEPRINTS.md`](../BLUEPRINTS.md) |
| 4 เชี่ยวชาญ | หน้าเว็บสำหรับผู้ใช้ · ห่อและรวมบริการ · ตรวจช่องโหว่ก่อนเปิดใช้ · บัญชีผู้ใช้ การขึ้น cloud และการแจ้งเตือน (ยังไม่มีในคู่มือ) | มีหน้าเว็บที่ต่อกับบริการได้ และมีรายการสิ่งที่ยังขาดก่อนเปิดให้คนทั่วไปใช้ | - | [`stack/examples/web/README.md`](../stack/examples/web/README.md), [`stack/THREAT-MODEL.md`](../stack/THREAT-MODEL.md), [`BLUEPRINTS.md`](../BLUEPRINTS.md) |

## Cybersecurity

คำถามของสายนี้: อะไรผิดพลาดได้ และกันไว้ตรงไหน (เชิงป้องกัน)

บทเรียนเป็นขั้นของสายนี้: [lessons/security.md](lessons/security.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | key คือความลับ · ข้อมูลอะไรออกจากเครื่อง · อย่าใส่เอกสารลับถ้าไม่ได้รับอนุญาต | ใช้คู่มือนี้โดยไม่ทำ key หรือเอกสารรั่ว | agent-kit, Git, Ollama, Python, งานอัตโนมัติ (automate.py), ไฟล์ .env | [`.env.example`](../.env.example), [`README.md`](../README.md) |
| 2 ปรับใช้ | สิทธิ์ขั้นต่ำของ tool · การขออนุมัติ · ที่อยู่ไฟล์ที่ออกนอกพื้นที่ · ข้อความที่มีคำสั่งแฝง | เขียน tool และไฟล์งานที่ทำได้เฉพาะสิ่งที่ตั้งใจ | audit log, Bash, robokit, SQL, unittest, การขออนุมัติ tool, ด่านตรวจคำสั่ง (robokit gate) | [`agent-kit/tools/_template.py`](../agent-kit/tools/_template.py), [`agent-kit/README.md`](../agent-kit/README.md), [`fields/robotics/robokit/README.md`](../fields/robotics/robokit/README.md) |
| 3 สร้างระบบ | ตรวจสิทธิ์ของบริการ · CORS และการจำกัดอัตรา · ช่องโหว่ในไลบรารี · audit log | เปิดบริการให้คนอื่นใช้โดยมีด่านพื้นฐานครบ | Express, GitHub Actions, npm audit, pip-audit | [`ai-api/README.md`](../ai-api/README.md), [`BLUEPRINTS.md`](../BLUEPRINTS.md) |
| 4 เชี่ยวชาญ | threat model ทั้งระบบ · เรียงลำดับสิ่งที่ต้องแก้ · แผนเมื่อเกิดเหตุ · sandbox ของ tool และการทดสอบเจาะ (ยังไม่มีในคู่มือ) | ประเมินความเสี่ยงของระบบ AI ทั้งระบบ และจัดลำดับสิ่งที่ต้องแก้ | - | [`stack/THREAT-MODEL.md`](../stack/THREAT-MODEL.md), [`hopekit/audit.py`](../hopekit/audit.py) |

## หุ่นยนต์

คำถามของสายนี้: คำสั่งจากโมเดลกลายเป็นการเคลื่อนที่ที่ปลอดภัยได้อย่างไร

บทเรียนเป็นขั้นของสายนี้: [lessons/robotics.md](lessons/robotics.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | จากคำสั่งถึงการเคลื่อนที่ · ทำไมต้องมีด่านตรวจ · จำลองก่อนฮาร์ดแวร์ | รันเดโมและอธิบายได้ว่าแต่ละชั้นทำหน้าที่อะไร | Python, เดโมจากหัวใจสู่กลไก | [`fields/robotics/01-heart-to-mechanism.md`](../fields/robotics/01-heart-to-mechanism.md), [`fields/robotics/heart-to-mechanism/simulate.py`](../fields/robotics/heart-to-mechanism/simulate.py) |
| 2 ปรับใช้ | ไฟล์กฎความปลอดภัย · PID · ระยะหยุด · วางแผนโปรเจกต์ | เขียนกฎและค่าควบคุมสำหรับกลไกของตัวเองในแบบจำลอง | NumPy, robokit, ด่านตรวจคำสั่ง (robokit gate) | [`fields/robotics/robokit/README.md`](../fields/robotics/robokit/README.md) |
| 3 สร้างระบบ | ตัวจำลองฟิสิกส์ · ต่อโมเดลภาษาเข้ากับคำสั่งหุ่นยนต์ · ชั้นป้องกันที่แยกจากซอฟต์แวร์ | ทดสอบทั้งระบบในโลกจำลองก่อนต่อฮาร์ดแวร์ | Gazebo, MuJoCo | [`fields/robotics/README.md`](../fields/robotics/README.md), [`domains/robotics/ros2_llm_bridge.py`](../domains/robotics/ros2_llm_bridge.py) |
| 4 เชี่ยวชาญ | ROS 2 · ฮาร์ดแวร์จริงและมาตรฐานความปลอดภัย · โมเดลที่รับภาพแล้วสั่งการ | นำระบบขึ้นฮาร์ดแวร์จริงโดยมีชั้นป้องกันอิสระ | C++, ROS 2, Rust | [`fields/robotics/README.md`](../fields/robotics/README.md) |

## คณิตศาสตร์

คำถามของสายนี้: ทำไมวิธีนี้ถึงใช้ได้

บทเรียนเป็นขั้นของสายนี้: [lessons/math.md](lessons/math.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | ร้อยละและค่าเฉลี่ย · อ่านกราฟ · ความน่าจะเป็นเบื้องต้น | อ่านผลทดสอบในคู่มือนี้ได้ว่าตัวเลขหมายถึงอะไร | Python, เดโมจากหัวใจสู่กลไก | [`catalog.json`](../catalog.json) |
| 2 ปรับใช้ | เวกเตอร์และความใกล้กัน · การให้คะแนนคำ (BM25) · recall และ precision | เข้าใจว่าทำไมการค้นได้ผลแบบนี้ และวัดได้ว่าดีแค่ไหน | BM25 (rank-bm25), FAISS, NumPy, robokit, sentence-transformers | [`rag-pipeline/retrieve.py`](../rag-pipeline/retrieve.py), [`rag-pipeline/README.md`](../rag-pipeline/README.md) |
| 3 สร้างระบบ | สมการการเคลื่อนที่ · ระบบควบคุมป้อนกลับ (PID) · ความคลาดเคลื่อนของการวัด | คำนวณและตรวจค่าควบคุมกับระยะหยุดด้วยมือได้ | - | [`fields/robotics/robokit/README.md`](../fields/robotics/robokit/README.md), [`fields/robotics/01-heart-to-mechanism.md`](../fields/robotics/01-heart-to-mechanism.md) |
| 4 เชี่ยวชาญ | พีชคณิตเชิงเส้น · การหาค่าเหมาะที่สุด · สถิติของการทดลอง · จำนวนเชิงซ้อนและ qubit | อ่านงานวิจัยและตัดสินได้ว่าผลที่อ้างน่าเชื่อแค่ไหน | Qiskit | [`domains/quantum/qiskit_intro.py`](../domains/quantum/qiskit_intro.py) |

## ปรัชญา

คำถามของสายนี้: เรารู้ได้อย่างไรว่าใช้ได้ และใครรับผิดชอบ

บทเรียนเป็นขั้นของสายนี้: [lessons/philosophy.md](lessons/philosophy.md)

| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |
|---|---|---|---|---|
| 1 เริ่มใช้ | โมเดลตอบผิดได้อย่างมั่นใจ · ตรวจกับแหล่งอ้างอิง · ทดสอบแล้ว กับ ยังไม่ได้ทดสอบ | ไม่เชื่อคำตอบของ AI โดยไม่ตรวจ และรู้ว่าตรวจกับอะไร | - | [`catalog.json`](../catalog.json), [`rag-pipeline/README.md`](../rag-pipeline/README.md) |
| 2 ปรับใช้ | ตรรกะ: ข้อสรุปตามมาจากหลักฐานไหม · เหตุผลวิบัติที่พบบ่อย · ข้อมูล กับ คำสั่ง | แยกได้ว่าข้อความไหนเป็นหลักฐาน ข้อความไหนเป็นแค่ข้ออ้าง | audit log, llm-eval, การขออนุมัติ tool | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| 3 สร้างระบบ | ญาณวิทยา: รู้ได้อย่างไรว่าจริง · ความมั่นใจที่โมเดลรายงานเอง · ใครอนุมัติและใครรับผิดชอบ | ออกแบบจุดที่คนต้องตัดสินใจ และบันทึกการตัดสินใจนั้น | - | [`agent-kit/README.md`](../agent-kit/README.md), [`fields/robotics/01-heart-to-mechanism.md`](../fields/robotics/01-heart-to-mechanism.md) |
| 4 เชี่ยวชาญ | จริยศาสตร์ของระบบที่ลงมือแทนคน · โมเดลเข้าใจจริงหรือไม่ · ผลระยะยาวต่อคนและงาน | ตัดสินได้ว่าระบบไหนควรสร้าง ไม่ใช่แค่สร้างได้หรือไม่ | - | [`ROADMAP.md`](../ROADMAP.md) |

ลิงก์ในช่อง "ในคู่มือ" ชี้ไปยังต้นแบบหรือเอกสารที่ใช้ในระดับนั้น ส่วนขั้นที่ต้องทำตามลำดับ และเกณฑ์ว่าผ่านระดับ อยู่ในบทเรียนของแต่ละสาย หัวข้อที่เขียนว่า "ยังไม่มีในคู่มือ" คือความรู้ที่สายนั้นต้องใช้ แต่คู่มือนี้ยังไม่ได้ทำ
