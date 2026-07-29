"""Tests for build_dashboard.py — 数据合并、周期评分、标记正确性。"""

import importlib.util
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("build_dashboard", _SCRIPTS / "build_dashboard.py")
_dash = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dash)


class TestBuildDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_generates_valid_payload(self):
        payload = _dash.build_dashboard(self.root)
        self.assertIsInstance(payload, dict)
        self.assertIn("meta", payload)
        self.assertIn("overview", payload)
        self.assertIn("token_pricing", payload)
        self.assertIn("business", payload)
        self.assertIn("compute", payload)
        self.assertIn("health", payload)
        self.assertIn("sources", payload)

    def test_pricing_records_have_required_fields(self):
        payload = _dash.build_dashboard(self.root)
        records = payload.get("token_pricing", {}).get("records", [])
        if records:
            for rec in records:
                self.assertIn("metric_id", rec)
                self.assertIn("confidence", rec)
                self.assertIn("region", rec)

    def test_sample_records_not_mislabeled_as_verified(self):
        """⚠️ sample 数据绝对不能标记为 verified。"""
        payload = _dash.build_dashboard(self.root)
        for rec in payload.get("token_pricing", {}).get("records", []):
            if rec.get("confidence") == "sample":
                self.assertNotEqual(rec.get("evidence_status"), "company_disclosure")
                self.assertIn("sample", " ".join(rec.get("tags", []) + [rec.get("note", "")]).lower())

    def test_missing_records_have_null_value(self):
        """missing 数据的 value 必须是 null，不是 0。"""
        payload = _dash.build_dashboard(self.root)
        for rec in payload.get("business", {}).get("records", []):
            if rec.get("confidence") == "missing":
                self.assertIsNone(rec.get("value"),
                    f"{rec.get('metric_id')} is missing but value is not None — 不能把 missing 写成 0")

    def test_cycle_scores_structure(self):
        payload = _dash.build_dashboard(self.root)
        cycle = payload.get("overview", {}).get("cycle", {})
        self.assertIn("stage_id", cycle)
        self.assertIn("stage_label", cycle)
        self.assertIn("industry_development_score", cycle)
        self.assertIn("confidence", cycle)
        # 第一期只有 sample 数据或无数据时，应标记 confidence=low
        self.assertIn(cycle.get("confidence", ""), ("low", "medium", "missing"))

    def test_health_structure(self):
        payload = _dash.build_dashboard(self.root)
        health = payload["health"]
        self.assertIn("sources_ok", health)
        self.assertIn("sources_total", health)
        self.assertIn("pricing_sample", health)

    def test_determine_stage_low_industry(self):
        stages = _dash._shared.load_json(
            self.root / "config" / "cycle_factors.json", {}
        ).get("stages", [])
        sid, _ = _dash._determine_stage(20, 40, stages)
        self.assertEqual(sid, "tech_validation")

    def test_determine_stage_high_industry_low_risk(self):
        stages = _dash._shared.load_json(
            self.root / "config" / "cycle_factors.json", {}
        ).get("stages", [])
        sid, _ = _dash._determine_stage(60, 40, stages)
        self.assertEqual(sid, "commercialization")

    def test_determine_stage_high_risk_crowded(self):
        stages = _dash._shared.load_json(
            self.root / "config" / "cycle_factors.json", {}
        ).get("stages", [])
        sid, _ = _dash._determine_stage(65, 75, stages)
        self.assertEqual(sid, "valuation_crowding")


if __name__ == "__main__":
    unittest.main()
