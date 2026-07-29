"""Tests for run_all.py — 编排器、skip-fetch、整体流水线。"""

import importlib.util
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("run_all", _SCRIPTS / "run_all.py")
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)


class TestRunAll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

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
