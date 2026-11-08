"""catalog.json ต้องครบฟิลด์ ไม่ซ้ำ และชี้ไปยัง path ที่มีอยู่จริง"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hope  # noqa: E402


class CatalogTest(unittest.TestCase):
    def test_catalog_is_valid(self):
        self.assertEqual(hope.catalog_problems(), [])

    def test_every_top_level_blueprint_is_listed(self):
        listed = {m["path"].rstrip("/") for m in hope.load_catalog()}
        for folder in ("rag-pipeline", "agent-kit", "llm-eval", "ai-api", "local-models", "languages", "domains"):
            self.assertIn(folder, listed)

    def test_links_checker_finds_nothing_broken(self):
        _checked, bad = hope.broken_links()
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
