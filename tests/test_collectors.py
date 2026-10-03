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


def _resolve_root():
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    unittest.main()
