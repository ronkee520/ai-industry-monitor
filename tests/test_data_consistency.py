"""Tests for data consistency across token_pricing, template, candidates, models, companies."""

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDataConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tp = json.loads(
            (ROOT / "data" / "manual" / "token_pricing.json").read_text(encoding="utf-8"))
        cls.tp_ids = {r["model_id"] for r in cls.tp["records"]}

        with (ROOT / "data" / "manual" / "manual_pricing_template.csv").open(
            encoding="utf-8-sig") as f:
            cls.tmpl_ids = {row["model_id"].strip() for row in csv.DictReader(f)}

        cls.cj = json.loads(
            (ROOT / "data" / "manual" / "pricing_candidates.json").read_text(encoding="utf-8"))
        cls.cj_ids = {c["model_id"] for c in cls.cj["candidates"]}

        cls.models = json.loads(
            (ROOT / "config" / "models.json").read_text(encoding="utf-8"))
        cls.model_ids = {m["id"] for m in cls.models["models"]}

        cls.companies = json.loads(
            (ROOT / "config" / "companies.json").read_text(encoding="utf-8"))
        cls.company_ids = {c["id"] for c in cls.companies["companies"]}

    # ── Cross-file consistency ──────────────────────────────────
    def test_template_model_ids_in_token_pricing(self):
        missing = self.tmpl_ids - self.tp_ids
        self.assertEqual(missing, set(),
            f"模板中的 model_id 不在 token_pricing.json: {missing}")

    def test_candidate_model_ids_in_token_pricing(self):
        missing = self.cj_ids - self.tp_ids
        self.assertEqual(missing, set(),
            f"候选数据中的 model_id 不在 token_pricing.json: {missing}")

    def test_token_pricing_model_ids_in_config_models(self):
        missing = self.tp_ids - self.model_ids
        self.assertEqual(missing, set(),
            f"token_pricing 中的 model_id 不在 config/models.json: {missing}")

    def test_token_pricing_company_ids_in_config_companies(self):
        tp_company_ids = {r["company_id"] for r in self.tp["records"]}
        missing = tp_company_ids - self.company_ids
        self.assertEqual(missing, set(),
            f"token_pricing 中的 company_id 不在 config/companies.json: {missing}")

    # ── Source URLs ─────────────────────────────────────────────
    def test_all_records_have_source_url(self):
        missing_url = [r["metric_id"] for r in self.tp["records"]
                       if not r.get("source_url")]
        self.assertEqual(missing_url, [],
            f"缺少 source_url: {missing_url}")

    # ── Manual_required invariants ──────────────────────────────
    def test_manual_required_has_null_value(self):
        bad = [r["metric_id"] for r in self.tp["records"]
               if r.get("confidence") == "manual_required" and r.get("value") is not None]
        self.assertEqual(bad, [],
            f"manual_required 记录 value 必须为 null: {bad}")

    def test_manual_required_not_verified(self):
        bad = [r["metric_id"] for r in self.tp["records"]
               if r.get("confidence") == "manual_required"
               and r.get("evidence_status") in ("verified", "official_pricing")]
        # manual_required 的 evidence_status 也应匹配
        for r in self.tp["records"]:
            if r["confidence"] == "manual_required":
                self.assertIn(r.get("evidence_status", ""),
                    ("manual_required", "missing", "sample"),
                    f"{r['metric_id']}: confidence=manual_required 但 evidence_status={r.get('evidence_status')}")

    def test_no_missing_value_as_zero(self):
        bad = [r["metric_id"] for r in self.tp["records"]
               if r.get("value") == 0 and r.get("confidence") in ("missing", "manual_required")]
        self.assertEqual(bad, [],
            f"missing/manual_required 的 value 不能为 0: {bad}")

    # ── Record count ────────────────────────────────────────────
    def test_token_pricing_count(self):
        self.assertEqual(len(self.tp["records"]), 17,
            f"预期 17 条 token pricing 记录，实际 {len(self.tp['records'])}")

    def test_all_manual_required_not_verified(self):
        verified = [r for r in self.tp["records"] if r.get("confidence") == "verified"]
        self.assertEqual(verified, [],
            f"当前不应存在 verified 记录: {[r['metric_id'] for r in verified]}")

    # ── No absolute paths / API keys ────────────────────────────
    def test_no_absolute_paths_in_data_files(self):
        for path in [
            ROOT / "data" / "manual" / "token_pricing.json",
            ROOT / "data" / "manual" / "pricing_candidates.json",
        ]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("C:\\", content, f"{path.name} 含 C:\\")
            self.assertNotIn("/Users/", content, f"{path.name} 含 /Users/")

    def test_no_api_keys_in_data_files(self):
        for path in [
            ROOT / "data" / "manual" / "token_pricing.json",
            ROOT / "config" / "sources.json",
        ]:
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r'(?i)api[_-]?key\s*:\s*"[\w-]{8,}"', content),
                f"{path.name} 可能含硬编码 API key")
            self.assertNotIn("sk-", content, f"{path.name} 可能含 OpenAI key")


if __name__ == "__main__":
    unittest.main()
