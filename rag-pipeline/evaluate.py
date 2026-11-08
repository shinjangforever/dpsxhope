"""
evaluate.py — วัดคุณภาพ RAG pipeline ด้วย 3 metric
  1. recall@k          — retrieved chunks ครอบคลุม keyword ที่คาดหวังแค่ไหน
  2. context_precision — สัดส่วน chunk ที่ score เกิน threshold (retrieve ตรงแค่ไหน)
  3. faithfulness      — answer อ้างเกิน context หรือเปล่า (ตรวจด้วย LLM ที่ตั้งไว้)

รัน: python evaluate.py --cases eval_cases.json --min-recall 0.7
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np

import config
from retrieve import retrieve
from generate import complete, generate, format_context
from textutil import fold

# threshold สำหรับ context_precision: ถือว่า chunk "ตรง" ถ้า score เกินค่านี้
SCORE_THRESHOLD = 0.0


def load_cases(path: str) -> list[dict]:
    """อ่านชุดทดสอบ: [{"question": "...", "expected_keywords": ["..."]}]"""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit(f"ไม่พบชุดทดสอบใน {path}")
    return cases


def recall_at_k(question: str, expected_keywords: list[str], k: int = config.TOP_K) -> float:
    """สัดส่วน keyword ที่คาดหวัง ซึ่งปรากฏใน retrieved chunks (0..1)"""
    chunks = retrieve(question, top_k=k)
    combined = fold(" ".join(c["text"] for c in chunks))
    if not expected_keywords:
        return 0.0
    hits = sum(1 for kw in expected_keywords if fold(kw) in combined)
    return hits / len(expected_keywords)


def source_hit(chunks: list[dict], item: dict) -> tuple[bool, bool]:
    """
    ใช้เมื่อกรณีทดสอบมี "expected_source": คืน (chunk อันดับ 1 ถูก, มี chunk ถูกอยู่ใน top-k)
    chunk ถูก = มาจากไฟล์นั้น (เทียบชื่อไฟล์ไม่รวมนามสกุล) และมี keyword ที่คาดหวังอย่างน้อยหนึ่งคำ
    เข้มกว่า recall@k เพราะ keyword เดียวกันอาจอยู่ในเอกสารอื่น
    """
    want = Path(item["expected_source"]).stem

    def is_right(chunk: dict) -> bool:
        name = chunk["source"].replace("\\", "/").rsplit("/", 1)[-1]
        return Path(name).stem == want and any(fold(kw) in fold(chunk["text"]) for kw in item["expected_keywords"])

    flags = [is_right(c) for c in chunks]
    return bool(flags and flags[0]), any(flags)


def context_precision(question: str, k: int = config.TOP_K) -> float:
    """
    proxy ว่า retrieve ตรงแค่ไหน: สัดส่วน chunk ที่ score เกิน threshold
    (chunk ที่ score ต่ำ = ดึงมาเกิน/ไม่เกี่ยว) คืน 0..1
    """
    chunks = retrieve(question, top_k=k)
    if not chunks:
        return 0.0
    relevant = sum(1 for c in chunks if c["score"] > SCORE_THRESHOLD)
    return relevant / len(chunks)


def faithfulness_check(question: str, answer: str) -> dict:
    """ให้ LLM ตรวจว่า answer อ้างเกิน context หรือไม่"""
    context = format_context(retrieve(question))
    prompt = (
        f"Context:\n{context}\n\nQuestion: {question}\nAnswer: {answer}\n\n"
        'Reply with JSON only: {"faithful": true, "reason": "..."}'
    )
    try:
        raw = complete("You check whether an answer is fully supported by the context.", prompt)
        match = re.search(r"\{.*\}", raw, re.S)
        return json.loads(match.group(0)) if match else {"faithful": None, "reason": "parse error"}
    except Exception as exc:
        return {"faithful": None, "reason": str(exc)}


def run_eval(cases_path: str = "eval_cases.json", min_recall: float = 0.0, use_judge: bool = True) -> bool:
    """รันชุดทดสอบ แล้วคืน True เมื่อ recall ผ่านเกณฑ์"""
    cases = load_cases(cases_path)
    print("=== RAG Evaluation ===\n")
    k = config.TOP_K
    recall_scores = []
    precision_scores = []
    faithful_flags = []
    first_hits, topk_hits = [], []   # เฉพาะกรณีที่มี expected_source

    for item in cases:
        q = item["question"]

        r = recall_at_k(q, item["expected_keywords"], k)
        p = context_precision(q, k)
        recall_scores.append(r)
        precision_scores.append(p)
        if "expected_source" in item:
            first, in_topk = source_hit(retrieve(q, top_k=k), item)
            first_hits.append(first)
            topk_hits.append(in_topk)

        # ดึง chunks จริงครั้งเดียวเพื่อ generate คำตอบไปตรวจ faithfulness
        faith = {"faithful": None, "reason": "skipped"}
        if use_judge:
            chunks = retrieve(q, top_k=k)
            answer = generate(q, chunks)
            faith = faithfulness_check(q, answer)
        faithful_flags.append(faith.get("faithful"))

        print(f"Q: {q}")
        print(f"  recall@{k}:          {r:.2f}")
        print(f"  context_precision: {p:.2f}")
        print(f"  faithful:          {faith.get('faithful')} — {faith.get('reason')}")
        print()

    # ค่าเฉลี่ยรวม — faithful นับเฉพาะข้อที่ตัดสินได้ (ไม่ใช่ None)
    judged = [f for f in faithful_flags if f is not None]
    faithful_rate = (sum(1 for f in judged if f) / len(judged)) if judged else float("nan")

    print("=== สรุปเฉลี่ย ===")
    print(f"avg recall@{k}:          {np.mean(recall_scores):.2f}")
    print(f"avg context_precision: {np.mean(precision_scores):.2f}")
    if first_hits:
        print(f"source top-1:          {sum(first_hits)}/{len(first_hits)}")
        print(f"source top-{k}:          {sum(topk_hits)}/{len(topk_hits)}")
    print(f"faithful rate:         {faithful_rate:.2f} (จาก {len(judged)}/{len(cases)} ข้อที่ตัดสินได้)")
    passed = float(np.mean(recall_scores)) >= min_recall
    print(f"result:                {'pass' if passed else 'fail'} (min recall {min_recall:.2f})")
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ประเมินคุณภาพ RAG จากชุดทดสอบ")
    parser.add_argument("--cases", default="eval_cases.json")
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if run_eval(args.cases, args.min_recall, not args.no_judge) else 1)
