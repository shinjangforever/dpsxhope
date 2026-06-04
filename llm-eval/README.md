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

## Quick Start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
export GOOGLE_API_KEY=your_key  # optional

python evaluator.py --model claude-sonnet-4-6 --cases examples/basic.json
```

## เทคโนโลยี

Python · Anthropic SDK · Google Generative AI SDK
