"""Tests for scripts/_shared.py — shared utility functions."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

# Import shared module via importlib since there's no __init__.py
import importlib.util

_scripts = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("_shared", _scripts / "_shared.py")
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)


class TestLoadJson(unittest.TestCase):
    def test_loads_valid_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write('{"a": 1, "b": [2, 3]}')
            tmp = Path(f.name)
        try:
            result = _shared.load_json(tmp)
            self.assertEqual(result, {"a": 1, "b": [2, 3]})
        finally:
            tmp.unlink()

    def test_returns_default_for_missing_file(self):
        result = _shared.load_json(Path("/nonexistent/path.json"), default=[])
        self.assertEqual(result, [])

    def test_returns_default_for_bad_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("this is not json{{{")
            tmp = Path(f.name)
        try:
            result = _shared.load_json(tmp, default={"fallback": True})
            self.assertEqual(result, {"fallback": True})
        finally:
            tmp.unlink()

    def test_returns_none_when_default_not_given(self):
        result = _shared.load_json(Path("/nonexistent/path.json"))
        self.assertIsNone(result)


class TestAtomicWrite(unittest.TestCase):
    def test_writes_and_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subdir" / "test.json"
            data = {"key": "value", "nested": {"x": [1, 2, 3]}}
            _shared.atomic_write(path, data)
            self.assertTrue(path.exists())
            read_back = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(read_back, data)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "c" / "test.json"
            _shared.atomic_write(path, {"hello": "world"})
            self.assertTrue(path.exists())

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            _shared.atomic_write(path, {"version": 1})
            _shared.atomic_write(path, {"version": 2})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"version": 2})


class TestAppendAndReadJsonl(unittest.TestCase):
    def test_append_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.jsonl"
            _shared.append_jsonl(path, {"date": "2026-01-01", "value": 10})
            _shared.append_jsonl(path, {"date": "2026-01-02", "value": 20})
            rows = _shared.read_jsonl(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["date"], "2026-01-01")

    def test_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "deep" / "data.jsonl"
            _shared.append_jsonl(path, {"a": 1})
            self.assertTrue(path.exists())

    def test_dedupe_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dedupe.jsonl"
            _shared.append_jsonl(
                path,
                {"date": "2026-07-01", "metric_id": "x", "value": 100},
                dedupe_keys=["date", "metric_id"],
            )
            _shared.append_jsonl(
                path,
                {"date": "2026-07-01", "metric_id": "x", "value": 200},
                dedupe_keys=["date", "metric_id"],
            )
            _shared.append_jsonl(
                path,
                {"date": "2026-07-02", "metric_id": "x", "value": 300},
                dedupe_keys=["date", "metric_id"],
            )
            rows = _shared.read_jsonl(path)
            self.assertEqual(len(rows), 2)
            # 同 key 的记录应该被覆盖为最新值
            row1 = [r for r in rows if r["date"] == "2026-07-01"][0]
            self.assertEqual(row1["value"], 200)

    def test_read_empty_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            rows = _shared.read_jsonl(path)
            self.assertEqual(rows, [])

    def test_read_missing_file_returns_empty_list(self):
        rows = _shared.read_jsonl(Path("/no/such/file.jsonl"))
        self.assertEqual(rows, [])

    def test_skip_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text(
                '{"ok": true}\nnot valid json\n{"ok": false}\n',
                encoding="utf-8",
            )
            rows = _shared.read_jsonl(path, skip_bad_lines=True)
            self.assertEqual(len(rows), 2)


class TestTimeTools(unittest.TestCase):
    def test_now_shanghai_returns_datetime(self):
        dt = _shared.now_shanghai()
        self.assertIsInstance(dt, _shared.datetime)

    def test_today_shanghai_returns_iso_date(self):
        d = _shared.today_shanghai()
        self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")

    def test_now_shanghai_is_utc_plus_8(self):
        dt = _shared.now_shanghai()
        self.assertEqual(dt.utcoffset().total_seconds(), 8 * 3600)


class TestHashContent(unittest.TestCase):
    def test_same_content_same_hash(self):
        h1 = _shared.hash_content("hello world")
        h2 = _shared.hash_content("hello world")
        self.assertEqual(h1, h2)

    def test_different_content_different_hash(self):
        h1 = _shared.hash_content("hello world")
        h2 = _shared.hash_content("hello world!")
        self.assertNotEqual(h1, h2)

    def test_whitespace_normalized(self):
        h1 = _shared.hash_content("hello   world")
        h2 = _shared.hash_content("hello world")
        self.assertEqual(h1, h2)

    def test_returns_64_char_hex(self):
        h = _shared.hash_content("test")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestBlendedCost(unittest.TestCase):
    def test_normal_case(self):
        result = _shared.blended_cost(
            input_price=2.50,
            output_price=15.00,
        )
        # 2.50 × 0.65 + 15.00 × 0.35 = 1.625 + 5.25 = 6.875
        self.assertAlmostEqual(result, 6.875, places=6)

    def test_returns_none_when_input_missing(self):
        result = _shared.blended_cost(input_price=None, output_price=10.0)
        self.assertIsNone(result)

    def test_returns_none_when_output_missing(self):
        result = _shared.blended_cost(input_price=2.0, output_price=None)
        self.assertIsNone(result)

    def test_custom_weights(self):
        result = _shared.blended_cost(
            input_price=10.0,
            output_price=10.0,
            input_weight=0.5,
            output_weight=0.5,
        )
        self.assertAlmostEqual(result, 10.0, places=6)


class TestNormalizeCurrency(unittest.TestCase):
    def test_usd_passthrough(self):
        result = _shared.normalize_currency(100.0, "USD")
        self.assertEqual(result, 100.0)

    def test_cny_to_usd(self):
        result = _shared.normalize_currency(725.0, "CNY", fx={"cny_per_usd": 7.25})
        self.assertAlmostEqual(result, 100.0, places=6)

    def test_none_passthrough(self):
        result = _shared.normalize_currency(None, "CNY", fx={"cny_per_usd": 7.25})
        self.assertIsNone(result)

    def test_missing_fx_raises(self):
        with self.assertRaises(ValueError):
            _shared.normalize_currency(100.0, "CNY")

    def test_unsupported_currency_raises(self):
        with self.assertRaises(ValueError):
            _shared.normalize_currency(100.0, "EUR")


class TestFreshness(unittest.TestCase):
    def test_fresh(self):
        result = _shared.freshness("2026-07-28", today=date(2026, 7, 29))
        self.assertEqual(result["status"], "fresh")
        self.assertEqual(result["age_days"], 1)

    def test_stale(self):
        result = _shared.freshness("2026-07-01", today=date(2026, 7, 29))
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["age_days"], 28)

    def test_very_stale(self):
        result = _shared.freshness("2026-01-01", today=date(2026, 7, 29))
        self.assertEqual(result["status"], "very_stale")

    def test_missing(self):
        result = _shared.freshness(None, today=date(2026, 7, 29))
        self.assertEqual(result["status"], "missing")
        self.assertIsNone(result["age_days"])


class TestNormalizedMetric(unittest.TestCase):
    def test_builds_valid_record(self):
        record = _shared.normalized_metric(
            metric_id="token_blended_cost::openai::gpt4o::standard",
            metric_name="GPT-4o 混合成本",
            metric_category="token_pricing",
            value=6.875,
            unit="USD_per_1M_tokens",
            currency="USD",
            company_id="openai",
            model_id="gpt4o",
            region="overseas",
            period="2026-07",
            as_of_date="2026-07-29",
            collected_at="2026-07-29T09:00:00+08:00",
            source_name="OpenAI",
            source_url="https://platform.openai.com/docs/pricing",
            source_tier=1,
            evidence_status="official_pricing",
            confidence="verified",
            note="Test metric",
        )
        self.assertEqual(record["metric_id"], "token_blended_cost::openai::gpt4o::standard")
        self.assertEqual(record["value"], 6.875)
        self.assertEqual(record["source_tier"], 1)

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _shared.normalized_metric(
                metric_id="",
                metric_name="",
                metric_category="",
                value=None,
                unit="",
                currency=None,
                company_id=None,
                model_id=None,
                region="",
                period="",
                as_of_date="",
                collected_at=None,
                source_name="",
                source_url="",
                source_tier=1,
                evidence_status="",
                confidence="",
                note="",
            )
        self.assertIn("缺少必需字段", str(ctx.exception))

    def test_invalid_region_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _shared.normalized_metric(
                metric_id="x",
                metric_name="x",
                metric_category="x",
                value=0,
                unit="x",
                currency=None,
                company_id=None,
                model_id=None,
                region="invalid_region",
                period="x",
                as_of_date="2026-01-01",
                collected_at=None,
                source_name="x",
                source_url="https://x.com",
                source_tier=1,
                evidence_status="official_pricing",
                confidence="verified",
                note="x",
            )
        self.assertIn("region", str(ctx.exception))

    def test_invalid_source_tier_raises(self):
        with self.assertRaises(ValueError):
            _shared.normalized_metric(
                metric_id="x",
                metric_name="x",
                metric_category="x",
                value=0,
                unit="x",
                currency=None,
                company_id=None,
                model_id=None,
                region="overseas",
                period="x",
                as_of_date="2026-01-01",
                collected_at=None,
                source_name="x",
                source_url="https://x.com",
                source_tier=99,
                evidence_status="official_pricing",
                confidence="verified",
                note="x",
            )

    def test_invalid_evidence_status_raises(self):
        with self.assertRaises(ValueError):
            _shared.normalized_metric(
                metric_id="x",
                metric_name="x",
                metric_category="x",
                value=0,
                unit="x",
                currency=None,
                company_id=None,
                model_id=None,
                region="overseas",
                period="x",
                as_of_date="2026-01-01",
                collected_at=None,
                source_name="x",
                source_url="https://x.com",
                source_tier=1,
                evidence_status="bad_status",
                confidence="verified",
                note="x",
            )

    def test_invalid_confidence_raises(self):
        with self.assertRaises(ValueError):
            _shared.normalized_metric(
                metric_id="x",
                metric_name="x",
                metric_category="x",
                value=0,
                unit="x",
                currency=None,
                company_id=None,
                model_id=None,
                region="overseas",
                period="x",
                as_of_date="2026-01-01",
                collected_at=None,
                source_name="x",
                source_url="https://x.com",
                source_tier=1,
                evidence_status="official_pricing",
                confidence="not_valid",
                note="x",
            )

    def test_defaults_collected_at(self):
        record = _shared.normalized_metric(
            metric_id="x",
            metric_name="x",
            metric_category="x",
            value=0,
            unit="x",
            currency=None,
            company_id=None,
            model_id=None,
            region="overseas",
            period="x",
            as_of_date="2026-01-01",
            collected_at=None,  # 传入 None，函数自动填充当前时间
            source_name="x",
            source_url="https://x.com",
            source_tier=1,
            evidence_status="official_pricing",
            confidence="verified",
            note="x",
        )
        self.assertIsNotNone(record.get("collected_at"))
        self.assertIn("+08:00", record["collected_at"])


class TestFetchUrl(unittest.TestCase):
    """fetch_url 测试使用 Mock，不依赖真实互联网连接。"""

    def test_returns_structured_error_on_exception(self):
        """模拟网络异常：urlopen 抛出异常时应返回 ok=False + error 字段。"""
        import io
        from unittest.mock import patch

        def _raise_timeout(*args, **kwargs):
            raise TimeoutError("simulated timeout")

        with patch("urllib.request.urlopen", _raise_timeout):
            result = _shared.fetch_url("https://example.com", timeout=5)
        self.assertFalse(result["ok"])
        self.assertIn("TimeoutError", result["error"])
        self.assertIsNotNone(result["fetched_at"])

    def test_returns_ok_on_success(self):
        """模拟正常响应：返回 ok=True 且包含 text/content_hash。"""
        import io
        from unittest.mock import patch, MagicMock

        html = b"<html><body><p>Test pricing page</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.geturl.return_value = "https://example.com/pricing"
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.read.return_value = html
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _shared.fetch_url("https://example.com/pricing")

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["final_url"], "https://example.com/pricing")
        self.assertIn("Test pricing page", result["text"])
        self.assertEqual(len(result["content_hash"]), 64)
        self.assertGreater(result["text_chars"], 0)

    def test_return_structure(self):
        """验证返回 dict 始终包含全部必需字段。"""
        required = {"ok", "status", "url", "final_url", "text",
                    "content_hash", "text_chars", "error", "fetched_at"}
        from unittest.mock import patch

        def _raise(*args, **kwargs):
            raise ConnectionError("no network")

        with patch("urllib.request.urlopen", _raise):
            result = _shared.fetch_url("https://example.com")
        self.assertTrue(required.issubset(result.keys()))


class TestResolveProjectRoot(unittest.TestCase):
    def test_resolves_from_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _shared.resolve_project_root(tmp)
            self.assertEqual(str(root), str(Path(tmp).resolve()))

    def test_resolves_from_implicit_path(self):
        """不传参数时，应推导到 scripts/.. = 项目根。"""
        root = _shared.resolve_project_root()
        expected = (Path(__file__).resolve().parents[1])
        self.assertEqual(root, expected)

    def test_raises_for_nonexistent_path(self):
        with self.assertRaises(FileNotFoundError):
            _shared.resolve_project_root("/no/such/directory")


class TestVisibleText(unittest.TestCase):
    def test_strips_script_and_style(self):
        html = "<html><head><style>body{}</style></head><body><p>Hello World</p><script>alert(1)</script></body></html>"
        text = _shared.visible_text(html)
        self.assertIn("Hello World", text)
        self.assertNotIn("alert(1)", text)
        self.assertNotIn("body{}", text)

    def test_collapses_whitespace(self):
        html = "<p>hello    world</p><p>foo  bar</p>"
        text = _shared.visible_text(html)
        self.assertEqual(text, "hello world foo bar")


class TestNoAbsolutePaths(unittest.TestCase):
    """确保代码中不存在本地绝对路径。"""

    def test_no_hardcoded_windows_paths(self):
        source = _scripts.joinpath("_shared.py").read_text(encoding="utf-8")
        self.assertNotIn("C:\\", source)
        self.assertNotIn("D:\\", source)
        self.assertNotIn("C:/", source)
        self.assertNotIn("D:/", source)

    def test_no_hardcoded_unix_home_paths(self):
        source = _scripts.joinpath("_shared.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", source)
        self.assertNotIn("/home/", source)


if __name__ == "__main__":
    unittest.main()
