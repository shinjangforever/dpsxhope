"""ทดสอบการค้นหาภาษาไทยด้วย BM25 + tokenizer (ไม่ใช้ embedding model จึงเร็วและรันใน CI ได้)

ชุดข้อมูล: rag-pipeline/sample_docs_th (8 ไฟล์) กับ eval_cases_th.json (30 ข้อ)
เกณฑ์ผ่านของแต่ละข้อ: ใน top-k ต้องมี chunk จากไฟล์ที่ถูกต้อง และมี keyword ที่คาดหวังอยู่ใน chunk นั้น
ซึ่งเข้มกว่า recall@k ของ evaluate.py เพราะ keyword เดียวกันอาจอยู่ในเอกสารอื่น (เช่น "สามสิบวัน")

นี่คือด่านกันถอยหลัง ไม่ใช่ benchmark: เอกสารและคำถามเขียนโดยผู้ดูแล repo เอง
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAG = ROOT / "rag-pipeline"
sys.path.insert(0, str(RAG))

from textutil import clean_extracted_text, fold  # noqa: E402

HAS_BM25 = importlib.util.find_spec("rank_bm25") is not None
HAS_PYPDF = importlib.util.find_spec("pypdf") is not None

if HAS_BM25:
    from rank_bm25 import BM25Okapi

    from chunking import chunk_document
    from textutil import tokenize

TOP_K = 4
MIN_SOURCE_HIT = 0.95  # สัดส่วนข้อที่ต้องเจอทั้งไฟล์และ keyword ใน top-4
MIN_TOP1 = 0.8         # สัดส่วนข้อที่ chunk อันดับ 1 ต้องถูก


def build():
    chunks = []
    for path in sorted((RAG / "sample_docs_th").glob("*.md")):
        chunks.extend(chunk_document(path.read_text(encoding="utf-8"), path.name))
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    return chunks, bm25


def rank(chunks, bm25, question, k=TOP_K):
    scores = bm25.get_scores(tokenize(question))
    order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:k]
    return [chunks[i] for i in order]


def is_hit(chunk, case):
    text = chunk["text"].lower()
    return chunk["source"] == case["expected_source"] and any(kw.lower() in text for kw in case["expected_keywords"])


@unittest.skipUnless(HAS_BM25, "ต้องติดตั้ง rank-bm25")
class ThaiSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((RAG / "eval_cases_th.json").read_text(encoding="utf-8"))
        cls.chunks, cls.bm25 = build()

    def test_corpus_and_cases_are_consistent(self):
        sources = {p.name for p in (RAG / "sample_docs_th").glob("*.md")}
        self.assertGreaterEqual(len(self.cases), 30)
        for case in self.cases:
            self.assertIn(case["expected_source"], sources, case["question"])
            doc = (RAG / "sample_docs_th" / case["expected_source"]).read_text(encoding="utf-8").lower()
            for kw in case["expected_keywords"]:
                self.assertIn(kw.lower(), doc, f"keyword ไม่อยู่ในเอกสาร: {kw}")

    def test_expected_chunk_is_in_top_k(self):
        misses = [c["question"] for c in self.cases
                  if not any(is_hit(ch, c) for ch in rank(self.chunks, self.bm25, c["question"]))]
        rate = 1 - len(misses) / len(self.cases)
        self.assertGreaterEqual(rate, MIN_SOURCE_HIT, f"ไม่เจอ {len(misses)} ข้อ: {misses}")

    def test_expected_chunk_is_first_often_enough(self):
        firsts = sum(is_hit(rank(self.chunks, self.bm25, c["question"], k=1)[0], c) for c in self.cases)
        rate = firsts / len(self.cases)
        self.assertGreaterEqual(rate, MIN_TOP1, f"top-1 ถูก {firsts}/{len(self.cases)}")

    def test_shared_keyword_does_not_confuse_documents(self):
        # "สามสิบ" อยู่ใน 3 เอกสาร (ลาป่วย, คืนสินค้า, ข้าวเหนียว) คำถามต้องพาไปถูกไฟล์
        for question, source in (
            ("คืนของได้ภายในกี่วัน", "customer-returns.md"),
            ("นึ่งข้าวเหนียวนานเท่าไร", "kitchen-recipes.md"),
            ("ลาป่วยได้กี่วันต่อปี", "hr-policy.md"),
        ):
            with self.subTest(question=question):
                self.assertEqual(rank(self.chunks, self.bm25, question, k=1)[0]["source"], source)



class ThaiPdfRepairTest(unittest.TestCase):
    # ข้อความดึงจาก PDF จริงที่ Edge สร้าง: ไม้เอกที่ซ้อนบนสระและการันต์กลายเป็น NUL,
    # สระอำถูกแยกเป็นนิคหิต+สระอา และมีช่องว่างแทรกก่อนวรรณยุกต์
    RAW = "ลาพักร ้อน\nพนักงานประจํามีสิทธิ\x00ลาพักร้อนสิบวันต่อปี ต้องยื\x00นคําขอล่วงหน้า"
    TRUE = "ลาพักร้อน\nพนักงานประจำมีสิทธิ์ลาพักร้อนสิบวันต่อปี ต้องยื่นคำขอล่วงหน้า"

    def test_cleans_nul_sara_am_and_stray_space(self):
        cleaned = clean_extracted_text(self.RAW)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("ํา", cleaned)
        self.assertIn("ลาพักร้อน", cleaned)

    def test_damaged_text_matches_true_text_after_fold(self):
        self.assertEqual(fold(self.RAW), fold(self.TRUE))
        self.assertEqual(tokenize(self.RAW), tokenize(self.TRUE))

    @unittest.skipUnless(HAS_PYPDF, "ต้องติดตั้ง pypdf")
    def test_real_pdf_fixture_is_searchable_by_keyword(self):
        from pypdf import PdfReader

        pdf = ROOT / "tests" / "fixtures" / "policy-th.pdf"
        raw = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
        self.assertIn("\x00", raw, "fixture ควรมีลักษณะที่เคยทำให้พัง ถ้าไม่มีแล้วให้ตรวจ pypdf เวอร์ชันใหม่")
        folded = fold(raw)
        for keyword in ("ลาพักร้อนสิบวัน", "สามสิบวัน", "เก้าสิบวัน", "เจ็ดวันทำการ"):
            with self.subTest(keyword=keyword):
                self.assertIn(fold(keyword), folded)


if __name__ == "__main__":
    unittest.main()
