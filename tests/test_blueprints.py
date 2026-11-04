import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent-kit"), str(ROOT / "rag-pipeline")]
os.environ["AGENT_AUDIT_LOG"] = str(Path(tempfile.gettempdir()) / "dpsxhope-test-audit.jsonl")

import tools  # noqa: E402
from textutil import tokenize  # noqa: E402
from tools.calculator import calculate  # noqa: E402
from tools.text_search import text_search  # noqa: E402


class CalculatorTest(unittest.TestCase):
    def test_allows_math(self):
        self.assertEqual(calculate("sqrt(65536)")["result"], 256.0)

    def test_blocks_python_objects(self):
        self.assertFalse(calculate("().__class__.__base__")["ok"])
        self.assertFalse(calculate("__import__('os')")["ok"])

    def test_blocks_large_powers(self):
        self.assertFalse(calculate("9**9**9")["ok"])


class ToolRegistryTest(unittest.TestCase):
    def test_discovers_tools_but_not_template(self):
        names = tools.discover()
        self.assertIn("calculate", names)
        self.assertIn("text_search", names)
        self.assertNotIn("lookup_customer", names)

    def test_run_reports_bad_arguments(self):
        result = tools.run(tools.select(["calculate"]), "calculate", {"wrong": "value"})
        self.assertIn("error", result)

    def test_search_stays_inside_root(self):
        self.assertIn("error", text_search("x", ".."))


class TokenizerTest(unittest.TestCase):
    def test_keeps_latin_words(self):
        self.assertEqual(tokenize("RAG pipeline v2"), ["rag", "pipeline", "v2"])

    def test_matches_thai_inside_sentences(self):
        document = set(tokenize("ระบบค้นหาเอกสารภาษาไทย"))
        query = tokenize("เอกสาร")
        self.assertTrue(query)
        self.assertTrue(set(query) <= document)


if __name__ == "__main__":
    unittest.main()
