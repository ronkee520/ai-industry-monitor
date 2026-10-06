"""Tests for collector scripts — importability, --project-root, dry-run, error handling."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# Import collectors
def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_token = _load("collect_token_pricing")
_gpu = _load("collect_gpu_pricing")
_news = _load("collect_news")
_biz = _load("collect_business_metrics")
_model_market = _load("collect_model_market_pricing")
_sec = _load("collect_sec_fundamentals")
_market = _load("collect_market_data")


class TestTokenPricingCollector(unittest.TestCase):
    def test_import_and_args(self):
        """脚本可导入，且支持 --project-root。"""
        self.assertTrue(hasattr(_token, "collect_token_pricing"))
        self.assertTrue(hasattr(_token, "parse_args"))

    def test_dry_run_no_write(self):
        """dry-run 不写入文件。"""
        root = _resolve_root()
        result = _token.collect_token_pricing(root, dry_run=True)
        self.assertIsInstance(result, dict)
        self.assertIn("fetched", result)

    def test_handles_missing_sources(self):
        """无配置时不崩溃。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True)
            (root / "config" / "sources.json").write_text('{}', encoding="utf-8")
            result = _token.collect_token_pricing(root, dry_run=True)
            self.assertEqual(result.get("status"), "skipped")

    def test_fetch_failure_preserves_last_good_fingerprint(self):
        source = {"id": "test", "company_id": "test", "kind": "official_pricing",
                  "name": "Test", "url": "https://example.com"}
        previous = {"test": {"content_hash": "abc", "checked_at": "2026-01-01T00:00:00+08:00",
                             "http_status": 200, "final_url": "https://example.com", "text_chars": 123}}
        with mock.patch.object(_token._shared, "fetch_url",
                               return_value={"ok": False, "error": "timeout"}):
            state = _token._fetch_source(source, previous)
        self.assertEqual(state["status"], "stale_fallback")
        self.assertEqual(state["content_hash"], "abc")
        self.assertEqual(state["last_successful_check"], "2026-01-01T00:00:00+08:00")


class TestGpuPricingCollector(unittest.TestCase):
    def test_import(self):
        self.assertTrue(hasattr(_gpu, "collect_gpu_pricing"))

    def test_dry_run(self):
        root = _resolve_root()
        result = _gpu.collect_gpu_pricing(root, dry_run=True)
        self.assertIsInstance(result, dict)
        self.assertIn("collector", result)

    def test_live_path_returns_summary(self):
        """非 dry-run 路径应返回摘要，防止采集完成后因未定义变量崩溃。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True)
            (root / "config" / "sources.json").write_text(
                '{"gpu_sources":[{"id":"gpu_test","provider":"Test","kind":"gpu_rental","name":"Test GPU","url":"https://example.com","enabled":true}]}',
                encoding="utf-8",
            )
            fake = {
                "ok": True,
                "status": 200,
                "final_url": "https://example.com",
                "text": "GPU pricing " * 20,
                "error": None,
            }
            with mock.patch.object(_gpu._shared, "fetch_url", return_value=fake):
                result = _gpu.collect_gpu_pricing(root)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["fetched"], 1)
            self.assertEqual(result["ok"], 1)
            self.assertEqual(result["errors"], 0)

    def test_failure_preserves_last_good_fingerprint(self):
        src = {"id": "gpu_test", "provider": "Test", "kind": "gpu_rental",
               "name": "Test GPU", "url": "https://example.com"}
        previous = {"content_hash": "abc", "checked_at": "2026-01-01T00:00:00+08:00",
                    "http_status": 200, "final_url": "https://example.com", "text_chars": 123}
        state = _gpu._gpu_state(src, {"ok": False, "error": "timeout"}, previous)
        self.assertEqual(state["status"], "stale_fallback")
        self.assertEqual(state["content_hash"], "abc")


class TestNewsCollector(unittest.TestCase):
    def test_import(self):
        self.assertTrue(hasattr(_news, "collect_news"))

    def test_dry_run(self):
        root = _resolve_root()
        result = _news.collect_news(root, dry_run=True)
        self.assertIsInstance(result, dict)


class TestBusinessCollector(unittest.TestCase):
    def test_import(self):
        self.assertTrue(hasattr(_biz, "collect_business_metrics"))

    def test_reads_manual_data(self):
        root = _resolve_root()
        result = _biz.collect_business_metrics(root, dry_run=True)
        self.assertIsInstance(result, dict)
        self.assertIn("stats", result)


class TestStructuredCollectors(unittest.TestCase):
    def test_model_market_dry_run(self):
        result = _model_market.collect_model_market_pricing(_resolve_root(), dry_run=True)
        self.assertGreater(result["models"], 10)

    def test_model_market_history_reconstructs_unchanged_days(self):
        records = [{
            "metric_id": "token_blended_cost::test::model::market_route",
            "provider_model_id": "test/model",
            "input_per_m": 2.0,
            "output_per_m": 6.0,
            "as_of_date": "2026-07-30",
        }]
        csv_text = (
            "date,event,source,provider,model,field,old,new\n"
            "2026-07-29,changed,openrouter,test,test/model,input_usd_per_mtok,1,2\n"
            "2026-07-29,changed,openrouter,test,test/model,output_usd_per_mtok,4,6\n"
        )
        payload = _model_market.build_market_price_history(
            records,
            csv_text,
            {"history_started_at": "2026-07-28", "history_url": "https://example.com/history.csv"},
        )
        self.assertEqual([row["date"] for row in payload["records"]], [
            "2026-07-28", "2026-07-29", "2026-07-30"
        ])
        self.assertEqual(payload["records"][0]["blended_cost_usd"], 2.05)
        self.assertEqual(payload["records"][1]["blended_cost_usd"], 3.4)
        self.assertEqual(payload["records"][2]["event_type"], "archived_price_interval")

    def test_sec_annual_fact_dedupes_restated_value(self):
        facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"start":"2024-01-01","end":"2024-12-31","filed":"2025-01-01","form":"10-K","fp":"FY","fy":2024,"val":10},
            {"start":"2024-01-01","end":"2024-12-31","filed":"2025-02-01","form":"10-K/A","fp":"FY","fy":2024,"val":11}
        ]}}}}}
        rows = _sec._annual_facts(facts, ("Revenues",))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["val"], 11)

    def test_lambda_parser_extracts_prices(self):
        html = "<table><tr><td>NVIDIA H100 SXM</td><td>80 GB</td><td>208</td><td>$3.99</td></tr></table>"
        rows = _gpu._parse_lambda_pricing({"provider":"Lambda","name":"Lambda","url":"https://lambda.ai/instances","tier":1}, html)
        self.assertEqual(rows[0]["gpu_model"], "NVIDIA H100 SXM")
        self.assertEqual(rows[0]["value"], 3.99)

    def test_runpod_parser_extracts_displayed_minimum(self):
        html = """<section>Thousands of GPUs across 30+ regions
        B300 288 GB HBM3e $7.89/hr H200 141 GB VRAM $4.59/hr
        H100 SXM secure cloud $3.49/hr community cloud $2.69/hr
        A100 SXM $1.59/hr Pro 6000 MIG 48GB $1.09/hr Serverless $9.99/hr</section>"""
        rows = _gpu._parse_runpod_pricing(
            {"provider":"RunPod","name":"RunPod","url":"https://www.runpod.io/pricing","tier":1}, html
        )
        by_model = {row["gpu_model"]: row for row in rows}
        self.assertEqual(by_model["NVIDIA B300"]["value"], 7.89)
        self.assertEqual(by_model["NVIDIA H200"]["value"], 4.59)
        self.assertEqual(by_model["NVIDIA H100 SXM"]["value"], 2.69)
        self.assertEqual(by_model["NVIDIA A100 SXM"]["value"], 1.59)
        self.assertEqual(by_model["NVIDIA H100 SXM"]["price_type"], "on_demand_displayed_min")

    def test_market_dry_run(self):
        result = _market.collect_market_data(_resolve_root(), dry_run=True)
        self.assertGreater(result["symbols"], 10)


def _resolve_root():
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    unittest.main()
