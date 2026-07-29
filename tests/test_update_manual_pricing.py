"""Tests for update_manual_pricing.py — CSV parsing, blended cost, confidence tagging."""

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "update_manual_pricing", _SCRIPTS / "update_manual_pricing.py"
)
_upd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_upd)

# Load shared
_shared_spec = importlib.util.spec_from_file_location("_shared", _SCRIPTS / "_shared.py")
_sh = importlib.util.module_from_spec(_shared_spec)
_shared_spec.loader.exec_module(_sh)


_WORKING_CSV = """company_id,company_name,model_id,model_name,source_url,input_price_per_m,output_price_per_m,cached_input_price_per_m,currency,tier,as_of_date,source_name,note
openai,OpenAI,gpt4o,GPT-4o,https://platform.openai.com/docs/pricing,2.50,10.00,1.25,USD,standard,,OpenAI,Test entry
anthropic,Anthropic,claude_opus4,Claude Opus 4,https://www.anthropic.com/pricing,,,,USD,standard,,Anthropic,No price filled
"""


class TestUpdateManualPricing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def setUp(self):
        # 还原 token_pricing.json 的备份
        self.pricing_path = self.root / "data" / "manual" / "token_pricing.json"
        self.backup = self.pricing_path.read_text(encoding="utf-8")

    def tearDown(self):
        self.pricing_path.write_text(self.backup, encoding="utf-8")

    # ── CSV parsing ───────────────────────────────────────────
    def test_load_template_reads_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            f.write(_WORKING_CSV)
            tmp = Path(f.name)
        try:
            rows = _upd.load_template(tmp)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["company_id"], "openai")
            self.assertEqual(rows[0]["input_price_per_m"], "2.50")
        finally:
            tmp.unlink()

    def test_load_template_rejects_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            _upd.load_template(Path("/no/such/template.csv"))

    # ── Dry-run ───────────────────────────────────────────────
    def test_dry_run_does_not_write(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            f.write(_WORKING_CSV)
            tmp = Path(f.name)
        try:
            before = json.loads(self.pricing_path.read_text(encoding="utf-8"))
            result = _upd.update_pricing(self.root, str(tmp), dry_run=True)
            after = json.loads(self.pricing_path.read_text(encoding="utf-8"))
            self.assertEqual(before, after,
                "dry-run 不应修改文件")
            self.assertGreater(result["updated"], 0,
                "dry-run 应报告将更新的记录数")
        finally:
            tmp.unlink()

    # ── Blended cost calculation ──────────────────────────────
    def test_blended_cost_correct(self):
        blended = _sh.blended_cost(2.50, 10.00)
        # 2.50 × 0.65 + 10.00 × 0.35 = 1.625 + 3.5 = 5.125
        self.assertAlmostEqual(blended, 5.125, places=6)

    def test_blended_cost_returns_none_when_missing(self):
        self.assertIsNone(_sh.blended_cost(None, 10.0))
        self.assertIsNone(_sh.blended_cost(2.0, None))
        self.assertIsNone(_sh.blended_cost(None, None))

    # ── Update with filled prices ─────────────────────────────
    def test_update_sets_verified_confidence(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            f.write(_WORKING_CSV)
            tmp = Path(f.name)
        try:
            _upd.update_pricing(self.root, str(tmp), dry_run=False)
            data = _sh.load_json(self.pricing_path, {})
            # GPT-4o should be verified
            gpt4o = [r for r in data["records"]
                     if r["company_id"] == "openai" and r["model_id"] == "gpt4o"]
            self.assertEqual(len(gpt4o), 1)
            self.assertEqual(gpt4o[0]["confidence"], "verified")
            self.assertEqual(gpt4o[0]["evidence_status"], "official_pricing")
            self.assertAlmostEqual(gpt4o[0]["value"], 5.125, places=4)
            self.assertNotIn("manual_required", gpt4o[0].get("tags", []))
            self.assertIn("verified", gpt4o[0].get("tags", []))
        finally:
            tmp.unlink()

    # ── Skip records without prices ───────────────────────────
    def test_no_price_stays_manual_required(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            f.write(_WORKING_CSV)
            tmp = Path(f.name)
        try:
            _upd.update_pricing(self.root, str(tmp), dry_run=False)
            data = _sh.load_json(self.pricing_path, {})
            # Claude Opus 4 未填价格，应保持 manual_required
            opus4 = [r for r in data["records"]
                      if r["company_id"] == "anthropic" and r["model_id"] == "claude_opus4"]
            self.assertEqual(len(opus4), 1)
            self.assertEqual(opus4[0]["confidence"], "manual_required")
            self.assertIsNone(opus4[0]["value"])
        finally:
            tmp.unlink()

    # ── Missing ≠ 0 ───────────────────────────────────────────
    def test_missing_price_not_written_as_zero(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            f.write(_WORKING_CSV)
            tmp = Path(f.name)
        try:
            _upd.update_pricing(self.root, str(tmp), dry_run=False)
            data = _sh.load_json(self.pricing_path, {})
            for r in data["records"]:
                if r["confidence"] == "manual_required":
                    self.assertIsNone(r["value"],
                        f"{r['metric_id']}: manual_required 但 value={r['value']} — 不能把空值当0")
        finally:
            tmp.unlink()

    # ── No absolute paths ─────────────────────────────────────
    def test_no_absolute_paths_in_script(self):
        source = (_SCRIPTS / "update_manual_pricing.py").read_text(encoding="utf-8")
        self.assertNotIn("C:\\", source)
        self.assertNotIn("D:\\", source)
        self.assertNotIn("/Users/", source)
        self.assertNotIn("/home/", source)

    # ── No API keys ───────────────────────────────────────────
    def test_no_api_keys_in_script(self):
        source = (_SCRIPTS / "update_manual_pricing.py").read_text(encoding="utf-8")
        # 只检查硬编码的 API key/secret/token 字符串（如 "sk-xxx"、"Bearer xxx" 等模式）
        import re
        self.assertIsNone(re.search(r'(?i)api[_-]?key\s*[:=]\s*[\"\'][\w-]{8,}[\"\']', source))
        self.assertIsNone(re.search(r'(?i)secret\s*[:=]\s*[\"\'][\w-]{8,}[\"\']', source))
        self.assertIsNone(re.search(r'(?i)password\s*[:=]\s*[\"\'][\w-]{6,}[\"\']', source))
        self.assertIsNone(re.search(r'(?i)bearer\s+[\w-]{8,}', source))
        # 不应有 sk- 开头的 OpenAI key 模式
        self.assertNotIn("sk-", source)


if __name__ == "__main__":
    unittest.main()
