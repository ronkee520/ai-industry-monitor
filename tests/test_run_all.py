"""Tests for run_all.py — 编排器、skip-fetch、整体流水线。"""

import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from tests._project_fixture import temporary_project

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("run_all", _SCRIPTS / "run_all.py")
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)


class TestRunAll(unittest.TestCase):
    def setUp(self):
        self.root = temporary_project(self.addCleanup, "config", "data", "web")

    def test_dry_run_keeps_snapshots_and_existing_site(self):
        site = self.root / "_site"
        site.mkdir()
        (site / "index.html").write_text("existing preview", encoding="utf-8")
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

        for skip_fetch in (False, True):
            with self.subTest(skip_fetch=skip_fetch):
                with mock.patch("urllib.request.urlopen") as fetch:
                    result = _run.run_all(self.root, skip_fetch=skip_fetch, dry_run=True)
                    fetch.assert_not_called()
                self.assertEqual(result["phases"]["build_dashboard"]["status"], "skipped")
                self.assertEqual(result["phases"]["build_site"]["status"], "skipped")
                after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
                self.assertEqual(before.keys(), after.keys())
                for path, contents in before.items():
                    self.assertEqual(contents, after[path], str(path.relative_to(self.root)))

    def test_skip_fetch_runs_without_network(self):
        """--skip-fetch 应跳过网络采集，直接用 local 数据构建。"""
        result = _run.run_all(self.root, skip_fetch=True, dry_run=False, verbose=False)
        self.assertIsInstance(result, dict)
        self.assertIn("phases", result)
        self.assertIn("elapsed_seconds", result)
        # build_site 应该成功
        site_phase = result["phases"].get("build_site", {})
        self.assertEqual(site_phase.get("status"), "ok",
            f"build_site 失败: {site_phase.get('error')}")

    def test_skip_fetch_preserves_history_and_shows_new_verified_price(self):
        history_dir = self.root / "data" / "history"
        last_run = _run._shared.read_jsonl(history_dir / "runs.jsonl")[-1]["generated_at"]
        last_collection = datetime.fromisoformat(last_run)
        verification_date = (last_collection.date() + timedelta(days=1)).isoformat()
        build_time = last_collection + timedelta(days=5)

        pricing_path = self.root / "data" / "manual" / "token_pricing.json"
        pricing = _run._shared.load_json(pricing_path)
        verified = next(row for row in pricing["records"] if row["confidence"] == "verified")
        metric_id = "token_blended_cost::test::new_official_model::standard"
        pricing["records"].append({
            **verified,
            "model_id": "new_official_model",
            "metric_id": metric_id,
            "as_of_date": verification_date,
        })
        _run._shared.atomic_write(pricing_path, pricing)
        _run._shared.append_jsonl(
            history_dir / "token_pricing.jsonl",
            {"date": verification_date, "metric_id": metric_id, "value": None},
        )
        history_before = {path: path.read_bytes() for path in history_dir.glob("*.jsonl")}

        with mock.patch.object(_run._shared, "now_shanghai", return_value=build_time):
            result = _run.run_all(self.root, skip_fetch=True)

        self.assertEqual(result["phases"]["build_site"]["status"], "ok")
        self.assertEqual(history_before, {path: path.read_bytes() for path in history_dir.glob("*.jsonl")})
        site_dir = self.root / "_site"
        published = _run._shared.load_json(site_dir / "api" / "history.json")
        official_points = [row for row in published["token_pricing"] if row["metric_id"] == metric_id]
        self.assertEqual([(row["date"], row["event_type"]) for row in official_points],
                         [(verification_date, "official_price_reference")])
        self.assertTrue(all(
            row.get("event_type") == "official_price_interval"
            for row in published["token_pricing"] if row["date"] == build_time.date().isoformat()
        ))
        self.assertIn(f"<time>{last_run}</time>", (site_dir / "index.html").read_text(encoding="utf-8"))

    def test_all_phases_present(self):
        result = _run.run_all(self.root, skip_fetch=True, dry_run=False, verbose=False)
        phases = result["phases"]
        expected = {"fetch", "build_dashboard", "build_site"}
        # fetch 被跳过时可能 key 不出现或以 "skipped" 状态出现
        for key in expected - {"fetch"}:
            self.assertIn(key, phases, f"缺少 phase: {key}")

    def test_verify_api_files_after_run(self):
        """运行后验证 _site/api/ 关键文件存在。"""
        _run.run_all(self.root, skip_fetch=True, dry_run=False, verbose=False)
        api_dir = self.root / "_site" / "api"
        for name in ("index.json", "dashboard.json", "overview.json",
                     "token-pricing.json", "business.json", "health.json"):
            self.assertTrue(
                (api_dir / name).exists(),
                f"构建后 _site/api/{name} 不存在"
            )

    def test_no_absolute_paths_in_scripts(self):
        """所有 scripts/ 下 Python 文件不包含本地绝对路径。"""
        for py_file in sorted(_SCRIPTS.glob("*.py")):
            content = py_file.read_text(encoding="utf-8")
            self.assertNotIn("C:\\", content, f"{py_file.name} 含 C:\\")
            self.assertNotIn("D:\\", content, f"{py_file.name} 含 D:\\")
            self.assertNotIn("/Users/", content, f"{py_file.name} 含 /Users/")
            self.assertNotIn("/home/", content, f"{py_file.name} 含 /home/")

    def test_no_api_keys_in_scripts(self):
        """所有 scripts/ 下 Python 文件不含硬编码的 API key/token/密码。"""
        import re
        patterns = [
            r'(?i)api[_-]?key\s*[:=]\s*["\'][a-zA-Z0-9_-]{20,}["\']',
            r'(?i)token\s*[:=]\s*["\'][a-zA-Z0-9_-]{20,}["\']',
            r'(?i)password\s*[:=]\s*["\'][^"\']+["\']',
            r'(?i)secret\s*[:=]\s*["\'][^"\']+["\']',
        ]
        for py_file in sorted(_SCRIPTS.glob("*.py")):
            content = py_file.read_text(encoding="utf-8")
            for pat in patterns:
                self.assertIsNone(
                    re.search(pat, content),
                    f"{py_file.name} 可能包含硬编码密钥 (pattern: {pat})"
                )


if __name__ == "__main__":
    unittest.main()
