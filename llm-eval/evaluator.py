"""
evaluator.py — วัดคุณภาพ LLM output ใน 3 มิติ:
  1. relevance   — ตอบตรงคำถามไหม
  2. faithfulness — อ้างอิงข้อมูลที่มีจริงไหม (hallucination check)
  3. format      — ตรง format ที่ระบุไหม

รัน: python evaluator.py --cases examples/cases.example.json --report report.json
"""
from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

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

    match = re.search(r"\{.*\}", resp.text, re.S)
    try:
        data = json.loads(match.group(0) if match else resp.text)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="ตรวจคำตอบ LLM จากชุดทดสอบ")
    parser.add_argument("--cases", required=True, help='ไฟล์ JSON: [{"question","answer","context"}]')
    parser.add_argument("--provider", choices=[p.value for p in Provider], default=Provider.ANTHROPIC.value)
    parser.add_argument("--report", help="บันทึกผลเป็นไฟล์ JSON")
    parser.add_argument("--min-relevance", type=float, default=0.0)
    parser.add_argument("--min-faithfulness", type=float, default=0.0)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit(f"ไม่พบชุดทดสอบใน {args.cases}")

    results = batch_evaluate(cases, Provider(args.provider))
    relevance = sum(r["relevance"] for r in results) / len(results)
    faithfulness = sum(r["faithfulness"] for r in results) / len(results)
    passed = relevance >= args.min_relevance and faithfulness >= args.min_faithfulness

    if args.report:
        report = {"passed": passed, "relevance": relevance, "faithfulness": faithfulness, "results": results}
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"result: {'pass' if passed else 'fail'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
