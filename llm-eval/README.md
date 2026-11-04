# llm-eval

LLM Evaluation framework — unified client สำหรับ Claude + Gemini พร้อม LLM-as-judge และ structured logging

## สถาปัตยกรรม

```
client.py          — unified LLM client (Claude + Gemini abstraction)
evaluator.py       — LLM-as-judge engine
logger.py          — structured eval result logger
examples/          — ตัวอย่าง eval runs
requirements.txt
```

## Features

- **Unified Client** — เรียก Claude และ Gemini ด้วย interface เดียวกัน
- **LLM-as-Judge** — ให้ Claude ตัดสิน output ด้วย rubric ที่กำหนดเอง
- **Pairwise Eval** — เปรียบเทียบ A vs B
- **Structured Logger** — บันทึกผลเป็น JSON พร้อม metadata

## เริ่มใช้งาน

```bash
pip install -r requirements.txt
cp ../.env.example ../.env   # ใส่ API key ของผู้ให้บริการที่ใช้
python examples/structured_output.py
python examples/few_shot.py
```

## นำไปใช้จริง

สร้างไฟล์ชุดทดสอบตามรูปแบบ [`examples/cases.example.json`](examples/cases.example.json) แล้วรัน:

```bash
python evaluator.py --cases my_cases.json --report report.json --min-relevance 0.8 --min-faithfulness 0.9
```

คำสั่งคืน exit code `1` เมื่อคะแนนต่ำกว่าเกณฑ์ จึงใช้เป็นด่านใน CI ได้ เลือก `--provider anthropic`, `gemini` หรือ `ollama`

**ข้อจำกัด:** LLM-as-judge ใช้ช่วยคัดกรอง ไม่ใช่คำตัดสินสุดท้าย ควรสุ่มตรวจด้วยคน โดยเฉพาะงานที่มีผลกระทบสูง

## เทคโนโลยี

Python · Anthropic SDK · Google GenAI SDK · Ollama
