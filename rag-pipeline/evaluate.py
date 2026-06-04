"""
evaluate.py — วัดคุณภาพ RAG pipeline ด้วย 3 metric
  1. recall@k          — retrieved chunks ครอบคลุม keyword ที่คาดหวังแค่ไหน
  2. context_precision — สัดส่วน chunk ที่ score เกิน threshold (retrieve ตรงแค่ไหน)
  3. faithfulness      — answer อ้างเกิน context หรือเปล่า (ตรวจด้วย Claude)

รัน: python evaluate.py
"""
import json

import anthropic
import numpy as np
from dotenv import load_dotenv

import config
from retrieve import retrieve
from generate import generate, format_context

# โหลด .env เพื่อให้ ANTHROPIC_API_KEY เข้ามาใน environment
load_dotenv()

# threshold สำหรับ context_precision: ถือว่า chunk "ตรง" ถ้า score เกินค่านี้
SCORE_THRESHOLD = 0.0

# ชุดทดสอบ — แต่ละข้อมีคำถาม + keyword ที่คาดว่าควรเจอใน chunks ที่ดึงมา
EVAL_SET = [
    {
        "question": "RAG คืออะไร?",
        "expected_keywords": ["retrieval", "augmented", "generation", "context"],
    },
    {
        "question": "vector search / embedding ทำงานยังไง?",
        "expected_keywords": ["embedding", "vector", "similarity", "nearest"],
    },
    {
        "question": "การ chunk เอกสารใน RAG ทำเพื่ออะไร?",
        "expected_keywords": ["chunk", "overlap", "size", "context"],
    },
]


def recall_at_k(question: str, expected_keywords: list[str], k: int = config.TOP_K) -> float:
    """สัดส่วน keyword ที่คาดหวัง ซึ่งปรากฏใน retrieved chunks (0..1)"""
    chunks = retrieve(question, top_k=k)
    combined = " ".join(c["text"].lower() for c in chunks)
    if not expected_keywords:
        return 0.0
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
    return hits / len(expected_keywords)


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
    """
    ใช้ Claude ตรวจว่า answer อ้างเกิน context (hallucinate) ไหม
    คืน {"faithful": bool, "reason": str} ; ถ้า parse json ไม่ได้ → faithful=None
    """
    try:
        client = anthropic.Anthropic(api_key=config.api_key())
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=(
                "คุณคือผู้ตรวจสอบความซื่อตรง (faithfulness) ของคำตอบ RAG "
                "ตอบกลับเป็น JSON ล้วนเท่านั้น ห้ามมีข้อความอื่น"
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"คำถาม: {question}\nคำตอบ: {answer}\n\n"
                        "คำตอบนี้กล่าวอ้างเกินสิ่งที่ควรมีหรือดูเหมือนแต่งขึ้นเอง "
                        "(unsupported / hallucinated) หรือไม่? "
                        'ตอบเป็น JSON: {"faithful": true/false, "reason": "..."}'
                    ),
                }
            ],
        )
        text = "".join(
            b.text for b in response.content if getattr(b, "type", None) == "text"
        )
        return json.loads(text)
    except Exception as e:
        # parse error หรือ api error → ไม่ตัดสิน
        return {"faithful": None, "reason": f"parse/api error: {e}"}


def run_eval() -> None:
    """วน EVAL_SET พิมพ์ 3 metric ต่อข้อ แล้วสรุปค่าเฉลี่ยรวมท้าย"""
    print("=== RAG Evaluation ===\n")
    k = config.TOP_K
    recall_scores = []
    precision_scores = []
    faithful_flags = []

    for item in EVAL_SET:
        q = item["question"]

        r = recall_at_k(q, item["expected_keywords"], k)
        p = context_precision(q, k)
        recall_scores.append(r)
        precision_scores.append(p)

        # ดึง chunks จริงครั้งเดียวเพื่อ generate คำตอบไปตรวจ faithfulness
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
    print(f"faithful rate:         {faithful_rate:.2f} (จาก {len(judged)}/{len(EVAL_SET)} ข้อที่ตัดสินได้)")


if __name__ == "__main__":
    run_eval()
