"""
evaluator.py — วัดคุณภาพ LLM output ใน 3 มิติ:
  1. relevance   — ตอบตรงคำถามไหม
  2. faithfulness — อ้างอิงข้อมูลที่มีจริงไหม (hallucination check)
  3. format      — ตรง format ที่ระบุไหม
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass

from client import chat, Provider


@dataclass
class EvalResult:
    relevance: float      # 0.0–1.0
    faithfulness: float   # 0.0–1.0
    format_ok: bool
    notes: str


_EVAL_PROMPT = """\
You are an objective LLM output evaluator.

Question: {question}
Context (ground truth): {context}
LLM Answer: {answer}

Score the answer on:
1. relevance (0.0-1.0): Does the answer address the question?
2. faithfulness (0.0-1.0): Is the answer supported by the context? Penalize hallucinations.
3. format_ok (true/false): Does the answer follow the requested format?

Reply with ONLY valid JSON, no markdown:
{{"relevance": 0.0, "faithfulness": 0.0, "format_ok": true, "notes": "..."}}
"""


def evaluate(
    question: str,
    answer: str,
    context: str = "",
    provider: Provider = Provider.ANTHROPIC,
) -> EvalResult:
    prompt = _EVAL_PROMPT.format(
        question=question,
        context=context or "(no context provided)",
        answer=answer,
    )
    resp = chat(prompt, system="You are an evaluator. Reply only with JSON.", provider=provider)

    raw = re.sub(r"```[a-z]*\n?", "", resp.text).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return EvalResult(relevance=0.0, faithfulness=0.0, format_ok=False, notes="parse error")

    return EvalResult(
        relevance=float(data.get("relevance", 0)),
        faithfulness=float(data.get("faithfulness", 0)),
        format_ok=bool(data.get("format_ok", False)),
        notes=str(data.get("notes", "")),
    )


def batch_evaluate(test_cases: list[dict], provider: Provider = Provider.ANTHROPIC) -> list[dict]:
    """รัน evaluate หลาย test cases พร้อมสรุปผล"""
    results = []
    for case in test_cases:
        result = evaluate(
            question=case["question"],
            answer=case["answer"],
            context=case.get("context", ""),
            provider=provider,
        )
        results.append({
            "question": case["question"],
            "relevance": result.relevance,
            "faithfulness": result.faithfulness,
            "format_ok": result.format_ok,
            "notes": result.notes,
        })

    avg_rel = sum(r["relevance"] for r in results) / len(results)
    avg_faith = sum(r["faithfulness"] for r in results) / len(results)
    print(f"\n=== Eval Summary ({len(results)} cases) ===")
    print(f"avg relevance:    {avg_rel:.2f}")
    print(f"avg faithfulness: {avg_faith:.2f}")
    return results
