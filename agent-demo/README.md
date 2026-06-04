# agent-demo

Agentic loop demo ด้วย Claude tool_use — แสดงให้เห็น agent ที่ตัดสินใจใช้ tools และ orchestrate workflows ได้เอง

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

## Quick Start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
python agent.py
```

## เทคโนโลยี

Python · Anthropic Claude · Tool Use API
