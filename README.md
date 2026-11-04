<p align="center">
  <img src="assets/banner/banner.png" alt="dpsxhope: แผนที่ความรู้และต้นแบบ AI ที่ใช้งานได้จริง" width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-c9a227" alt="Code license: MIT"></a>
  <a href="LICENSE-CONTENT.md"><img src="https://img.shields.io/badge/content-CC%20BY%204.0-c9a227" alt="Content license: CC BY 4.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-111111" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-20%2B-111111" alt="Node.js 20+">
  <img src="https://img.shields.io/badge/status-building-111111" alt="Status: building">
</p>

<p align="center">
  <a href="#เริ่มใน-5-นาที">เริ่มใน 5 นาที</a> ·
  <a href="#เลือกต้นแบบ">เลือกต้นแบบ</a> ·
  <a href="BLUEPRINTS.md">นำไปใช้จริง</a> ·
  <a href="ROADMAP.md">Roadmap</a> ·
  <a href="README.en.md">English</a>
</p>

**dpsxhope** คือคู่มือและชุดต้นแบบ AI engineering ภาษาไทย สำหรับนำไปปรับใช้กับเอกสาร ระบบ และงานจริงของคุณ

เนื้อหาเริ่มจาก RAG, agent, การประเมินผล และ AI API แล้วจะขยายเป็นแผนที่ความรู้ที่เชื่อม AI กับ robotics, anatomy, biology, quantum, business, games, sports และ 3D

## เลือกต้นแบบ

| ต้องการสร้าง | ต้นแบบ | ปรับใช้โดย | ต้องใช้ |
|---|---|---|---|
| **ถามตอบจากเอกสาร** | [`rag-pipeline`](rag-pipeline/) | ใส่โฟลเดอร์ `.txt`, `.md`, `.pdf` และชุดทดสอบของคุณ | Ollama หรือ API key |
| **ผู้ช่วยเรียกระบบภายใน** | [`agent-kit`](agent-kit/) | เพิ่มไฟล์ tool และ system prompt | API key |
| **ตรวจคุณภาพ AI** | [`llm-eval`](llm-eval/) | ใช้ชุดทดสอบของคุณและตั้งเกณฑ์ใน CI | Ollama หรือ API key |
| **บริการ API** | [`ai-api`](ai-api/) | ตั้ง auth, CORS, prompt และ deploy | Node.js, API key |

ก่อนเปิดให้ผู้อื่นใช้ อ่าน [คู่มือนำไปใช้จริง](BLUEPRINTS.md) ซึ่งมีจุดที่ต้องเปลี่ยน รายการตรวจ และแนวทางขยายระบบ

## เริ่มกับเอกสารของคุณ

ต้องมี Git และ Python 3.11 ขึ้นไป

```bash
git clone https://github.com/shinjangforever/dpsxhope.git
cd dpsxhope
python -m venv .venv
```

เปิดใช้งาน virtual environment:

```bash
# macOS, Linux, Termux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

ติดตั้งและสร้าง index:

```bash
pip install -r rag-pipeline/requirements.txt
cp .env.example .env
cd rag-pipeline
python pipeline.py ingest --docs /path/to/your-docs
```

เลือกวิธีสร้างคำตอบในไฟล์ `.env`:

| วิธี | ตั้งค่า |
|---|---|
| **Ollama ในเครื่อง** | `LLM_PROVIDER=ollama` และ `OLLAMA_MODEL=<ชื่อโมเดล>` |
| **Claude API** | `LLM_PROVIDER=anthropic` และ `ANTHROPIC_API_KEY=<key>` |

จากนั้นถามคำถาม:

```bash
python pipeline.py query "นโยบายลาพักร้อนคืออะไร"
```

ถ้ายังไม่มีเอกสาร ใช้ `sample_docs/` เพื่อทดลองก่อนได้

## โมดูลอ้างอิง

| โมดูล | ใช้ทำอะไร | ระดับ |
|---|---|---|
| [`local-models`](local-models/) | ควบคุม LLM engine, ตรวจสถานะ และจัด prompt format | เครื่องมืออ้างอิง |
| [`languages`](languages/) | รูปแบบ AI ในหลายภาษาโปรแกรม | ตัวอย่างอ้างอิง |
| [`domains`](domains/) | จุดเริ่มต้นสำหรับ robotics, quantum และ cloud | ตัวอย่างอ้างอิง |

## ตั้งค่าโมเดล

ทุกโมดูลอ่านไฟล์ `.env` ที่ root ของ repo เปลี่ยนรุ่นโมเดลได้โดยไม่ต้องแก้โค้ด

```env
CLAUDE_MODEL=claude-haiku-5-5
GEMINI_MODEL=gemini-3.5-flash
OLLAMA_MODEL=llama3.2
```

> [!WARNING]
> อย่า commit ไฟล์ `.env` และอย่าเปิด `ai-api` ออกอินเทอร์เน็ตโดยไม่ตั้ง `APP_API_KEY`

## ทดสอบ

```bash
python -m unittest discover -s tests
```

## หลักการ

- **เริ่มจากงานจริง:** ใช้ข้อมูล กติกา และชุดทดสอบของคุณแทนข้อมูลตัวอย่าง
- **บอกข้อจำกัด:** ทุกต้นแบบระบุสิ่งที่ยังต้องเพิ่มก่อนใช้จริง
- **เปลี่ยนได้:** ไม่ผูกกับผู้ให้บริการโมเดลเจ้าเดียว
- **นำไปต่อได้:** โค้ดและเนื้อหามี license ชัดเจน

## ร่วมพัฒนา

แก้คำสั่งที่พัง เพิ่มต้นแบบ หรือเสนอสาขาใหม่ได้ อ่านแนวทางใน [CONTRIBUTING.md](CONTRIBUTING.md) และดูทิศทางใน [ROADMAP.md](ROADMAP.md)

## License

โค้ดใช้ [MIT](LICENSE) และเนื้อหาใช้ [CC BY 4.0](LICENSE-CONTENT.md) ส่วนไฟล์จากบุคคลที่สามใช้ license ของเจ้าของเดิม

## ผู้สร้าง

**Daranpat Pattarakanpong (Shin)**
