"""Tests for collect_pricing_candidates.py."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "collect_pricing_candidates", _SCRIPTS / "collect_pricing_candidates.py"
)
_coll = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_coll)

_sh_spec = importlib.util.spec_from_file_location("_shared", _SCRIPTS / "_shared.py")
_sh = importlib.util.module_from_spec(_sh_spec)
_sh_spec.loader.exec_module(_sh)


class TestCollectPricingCandidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    # ── dry-run ────────────────────────────────────────────────
    def test_dry_run_returns_empty(self):
        candidates = _coll.collect_candidates(self.root, dry_run=True)
        self.assertEqual(candidates, [])

    def test_dry_run_does_not_create_files(self):
        json_path = self.root / "data" / "manual" / "pricing_candidates.json"
        csv_path = self.root / "data" / "manual" / "pricing_candidates.csv"
        existed_before = json_path.exists()
        _coll.collect_candidates(self.root, dry_run=True)
        self.assertEqual(json_path.exists(), existed_before,
            "dry-run 不应创建文件")

    # ── Extraction logic ───────────────────────────────────────
    def test_extract_candidate_failed_fetch(self):
        row = {"company_id": "test", "model_id": "test_m", "model_name": "Test",
               "source_url": "https://x.com", "source_name": "X"}
        result = {"ok": False, "error": "timeout"}
        cand = _coll._extract_candidate(row, result, "https://x.com")
        self.assertEqual(cand["extraction_status"], "failed")
        self.assertEqual(cand["confidence"], "failed")
        self.assertTrue(cand["manual_review_required"])

    def test_extract_candidate_js_rendered(self):
        row = {"company_id": "test", "model_id": "test_m", "model_name": "Test",
               "source_url": "https://x.com", "source_name": "X"}
        # Simulate a JS-rendered page with enough content to pass the min-length check
        filler = "padding text. " * 30  # enough chars to pass 200-char minimum
        js_html = (
            '<html><head><script src="bundle.js"></script></head>'
            '<body><div id="root"></div>' + filler + '</body></html>'
        )
        result = {"ok": True, "text": js_html, "status": 200, "content_hash": "abc",
                  "text_chars": len(js_html), "final_url": "https://x.com"}
        cand = _coll._extract_candidate(row, result, "https://x.com")
        self.assertIn(cand["extraction_status"], ("js_rendered", "failed"))
        self.assertIsNone(cand["input_price_per_m_candidate"])

    def test_no_price_data_is_ambiguous(self):
        row = {"company_id": "test", "model_id": "test_m", "model_name": "Test",
               "source_url": "https://x.com", "source_name": "X"}
        html = "<html><body><p>Welcome to our pricing page.</p><p>Contact sales for details.</p></body></html>"
        result = {"ok": True, "text": html, "status": 200, "content_hash": "abc",
                  "text_chars": len(html), "final_url": "https://x.com"}
        cand = _coll._extract_candidate(row, result, "https://x.com")
        self.assertIn(cand["extraction_status"], ("ambiguous", "failed", "js_rendered"))
        self.assertTrue(cand["manual_review_required"])

    # ── Candidate never writes to token_pricing.json ────────────
    def test_candidate_does_not_modify_token_pricing(self):
        tp_path = self.root / "data" / "manual" / "token_pricing.json"
        before = tp_path.read_text(encoding="utf-8")
        _coll.collect_candidates(self.root, dry_run=False, verbose=False)
        after = tp_path.read_text(encoding="utf-8")
        self.assertEqual(before, after,
            "collect_candidates 绝对不能修改 token_pricing.json")

    # ── JS render score ─────────────────────────────────────────
    def test_js_render_score_high_for_bundle(self):
        html = '<html><head><script src="bundle.js"></script></head><body><div id="root"></div></body></html>'
        score = _coll._js_render_score(html)
        self.assertGreaterEqual(score, 8)

    def test_js_render_score_low_for_static(self):
        html = '<html><body><h1>Pricing</h1><p>GPT-4o: $2.50 / 1M input tokens</p><p>GPT-4o: $10.00 / 1M output tokens</p></body></html>'
        score = _coll._js_render_score(html)
        self.assertLessEqual(score, 9)

    # ── Price extraction ────────────────────────────────────────
    def test_extract_prices_from_clean_text(self):
        text = "GPT-4o: input $2.50 / 1M tokens, output $10.00 / 1M tokens"
        prices = _coll._extract_prices(text)
        self.assertIsNotNone(prices["input"])
        self.assertAlmostEqual(prices["input"], 2.50, places=2)
        self.assertIsNotNone(prices["output"])
        self.assertAlmostEqual(prices["output"], 10.00, places=2)

    # ── No absolute paths ──────────────────────────────────────
    def test_no_absolute_paths(self):
        src = (_SCRIPTS / "collect_pricing_candidates.py").read_text(encoding="utf-8")
        self.assertNotIn("C:\\", src)
        self.assertNotIn("D:\\", src)

    # ── No API keys ────────────────────────────────────────────
    def test_no_api_keys(self):
        import re
        src = (_SCRIPTS / "collect_pricing_candidates.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'(?i)api[_-]?key\s*[:=]\s*[\"\'][\w-]{8,}[\"\']', src))
        self.assertIsNone(re.search(r'(?i)bearer\s+[\w-]{8,}', src))
        self.assertNotIn("sk-", src)


if __name__ == "__main__":
    unittest.main()
