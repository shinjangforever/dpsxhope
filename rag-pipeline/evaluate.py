"""
evaluate.py — วัดคุณภาพ RAG output: recall@k + faithfulness check
รัน: python evaluate.py
"""
import json
import os

import anthropic
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from query import retrieve, generate

load_dotenv()

EVAL_SET = [
    {
        "question": "What is RAG?",
        "expected_keywords": ["retrieval", "augmented", "generation", "context"],
    },
    {
        "question": "How does vector search work?",
        "expected_keywords": ["embedding", "vector", "similarity", "nearest"],
    },
]


def recall_at_k(question: str, expected_keywords: list[str], k: int = 4) -> float:
    """ตรวจว่า retrieved chunks ครอบคลุม keywords ที่คาดไว้"""
    chunks = retrieve(question, top_k=k)
    combined = " ".join(c["text"].lower() for c in chunks)
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
    return hits / len(expected_keywords)


def faithfulness_check(question: str, answer: str) -> dict:
    """ใช้ Claude ตรวจว่า answer hallucinate หรือเปล่า"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\nAnswer: {answer}\n\n"
                    "Rate this answer: does it make unsupported claims? "
                    "Reply with JSON: {\"faithful\": true/false, \"reason\": \"...\"}"
                ),
            }
        ],
    )
    try:
        return json.loads(response.content[0].text)
    except Exception:
        return {"faithful": None, "reason": "parse error"}


def run_eval() -> None:
    print("=== RAG Evaluation ===\n")
    recall_scores = []

    for item in EVAL_SET:
        q = item["question"]
        r = recall_at_k(q, item["expected_keywords"])
        recall_scores.append(r)

        chunks = retrieve(q)
        answer = generate(q, chunks)
        faith = faithfulness_check(q, answer)

        print(f"Q: {q}")
        print(f"  recall@4:    {r:.2f}")
        print(f"  faithful:    {faith['faithful']} — {faith['reason']}")
        print()

    print(f"avg recall@4: {np.mean(recall_scores):.2f}")


if __name__ == "__main__":
    run_eval()
