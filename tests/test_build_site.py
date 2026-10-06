"""Tests for build_site.py — multi-path pages, template vars, API endpoints."""

import importlib.util
import re
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("build_site", _SCRIPTS / "build_site.py")
_site_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_site_mod)

_shared_spec = importlib.util.spec_from_file_location("shared", _SCRIPTS / "_shared.py")
_shared = importlib.util.module_from_spec(_shared_spec)
_shared_spec.loader.exec_module(_shared)


class TestBuildSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        # 确保 dashboard.json 存在
        dash_spec = importlib.util.spec_from_file_location(
            "build_dashboard", _SCRIPTS / "build_dashboard.py")
        dash = importlib.util.module_from_spec(dash_spec)
        dash_spec.loader.exec_module(dash)
        dash.build_dashboard(cls.root)
        # 构建站点
        cls.site_dir = _site_mod.build_site(cls.root)

    # ── Directory structure ────────────────────────────────────
    def test_site_dir_exists(self):
        self.assertTrue(self.site_dir.exists())

    def test_nojekyll_exists(self):
        self.assertTrue((self.site_dir / ".nojekyll").exists())

    def test_index_html_exists(self):
        self.assertTrue((self.site_dir / "index.html").exists())

    def test_token_page_exists(self):
        self.assertTrue((self.site_dir / "token" / "index.html").exists())

    def test_business_page_exists(self):
        self.assertTrue((self.site_dir / "business" / "index.html").exists())

    def test_compute_page_exists(self):
        self.assertTrue((self.site_dir / "compute" / "index.html").exists())

    def test_methodology_page_exists(self):
        self.assertTrue((self.site_dir / "methodology" / "index.html").exists())

    def test_supply_chain_page_exists(self):
        self.assertTrue((self.site_dir / "supply-chain" / "index.html").exists())

    def test_investment_page_exists(self):
        self.assertTrue((self.site_dir / "investment" / "index.html").exists())

    # ── Static assets ──────────────────────────────────────────
    def test_app_js_copied(self):
        self.assertTrue((self.site_dir / "app.js").exists())

    def test_styles_css_copied(self):
        self.assertTrue((self.site_dir / "styles.css").exists())

    def test_site_wide_watermark_is_in_shared_styles(self):
        content = (self.site_dir / "styles.css").read_text(encoding="utf-8")
        self.assertIn("SUSTech%20Ren%20Keyi", content)
        self.assertIn("background-repeat: repeat", content)
        self.assertIn("pointer-events: none", content)

    def test_history_chart_handles_flat_and_single_point_series(self):
        """不变价格不能与横轴重合，单个快照也应显示为数据点。"""
        content = (self.site_dir / "app.js").read_text(encoding="utf-8")
        self.assertIn("span===0", content)
        self.assertIn("history-point", content)
        self.assertIn("仅 1 个有效快照", content)
        self.assertIn("价格未变", content)
        self.assertIn("history-range", content)
        self.assertIn("coverageDays", content)
        self.assertIn("official_price_effective", content)
        self.assertIn("每日真实快照", content)
        self.assertIn('rawValue===null||rawValue==="" ? NaN', content)

    def test_cycle_methodology_is_expandable_and_auditable(self):
        content = (self.site_dir / "app.js").read_text(encoding="utf-8")
        styles = (self.site_dir / "styles.css").read_text(encoding="utf-8")
        self.assertIn("评分公式、数据来源与本期完整计算", content)
        self.assertIn("renderCycleFactorBreakdown", content)
        self.assertIn("当前阶段如何判定", content)
        self.assertIn("deterioration_triggers", content)
        self.assertIn("cycle-methodology", styles)

    def test_price_history_uses_daily_schedule_and_extended_retention(self):
        dashboard_builder = (self.root / "scripts" / "build_dashboard.py").read_text(encoding="utf-8")
        workflow = (self.root / ".github" / "workflows" / "update-deploy.yml").read_text(encoding="utf-8")
        self.assertIn('price_history[-20000:]', dashboard_builder)
        self.assertIn('cron: "0 1 * * *"', workflow)

    def test_favicon_copied(self):
        self.assertTrue((self.site_dir / "favicon.svg").exists())

    # ── Template variables ─────────────────────────────────────
    def test_no_template_vars_in_home(self):
        content = (self.site_dir / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("{{ROOT_PREFIX}}", content)
        self.assertNotIn("{{ASSET_PREFIX}}", content)
        self.assertNotIn("{{ASSET_VERSION}}", content)
        self.assertNotIn("{{PRERENDERED_CONTENT}}", content)
        self.assertIn("BUILD-TIME SNAPSHOT", content)
        self.assertIn("数据截止", content)

    def test_no_template_vars_in_any_page(self):
        for html_file in self.site_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            self.assertNotIn("{{ROOT_PREFIX}}", content,
                f"{html_file.relative_to(self.site_dir)} 残留 ROOT_PREFIX")
            self.assertNotIn("{{ASSET_PREFIX}}", content,
                f"{html_file.relative_to(self.site_dir)} 残留 ASSET_PREFIX")
            self.assertNotIn("{{ASSET_VERSION}}", content,
                f"{html_file.relative_to(self.site_dir)} 残留 ASSET_VERSION")
            self.assertNotIn("{{PRERENDERED_CONTENT}}", content,
                f"{html_file.relative_to(self.site_dir)} 残留 PRERENDERED_CONTENT")

    def test_methodology_exposes_governance_and_disclaimer(self):
        app = (self.site_dir / "app.js").read_text(encoding="utf-8")
        html = (self.site_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn("企业采用少于3家公司时退出计分", app)
        self.assertIn("稳健性检验", app)
        self.assertIn("证据完整度不是概率", app)
        self.assertIn("不构成投资建议", html)

    # ── Path correctness ───────────────────────────────────────
    def test_home_uses_relative_assets(self):
        content = (self.site_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('./app.js', content)
        self.assertIn('./styles.css', content)
        self.assertIn('DASHBOARD_ROOT = "./"', content)

    def test_assets_use_content_version_for_cache_busting(self):
        for html_file in self.site_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            self.assertRegex(content, r'app\.js\?v=[0-9a-f]{12}')
            self.assertRegex(content, r'styles\.css\?v=[0-9a-f]{12}')

    def test_sub_pages_use_parent_assets(self):
        for sub in ("token", "business", "compute", "supply-chain", "investment", "methodology"):
            content = (self.site_dir / sub / "index.html").read_text(encoding="utf-8")
            self.assertIn('../app.js', content, f"{sub}/index.html 未引用 ../app.js")
            self.assertIn('../styles.css', content, f"{sub}/index.html 未引用 ../styles.css")
            self.assertIn('DASHBOARD_ROOT = "../"', content,
                f"{sub}/index.html DASHBOARD_ROOT 不是 ../")

    # ── API endpoints ──────────────────────────────────────────
    def test_api_index_json(self):
        self.assertTrue((self.site_dir / "api" / "index.json").exists())

    def test_api_dashboard_json(self):
        self.assertTrue((self.site_dir / "api" / "dashboard.json").exists())

    def test_api_overview_json(self):
        self.assertTrue((self.site_dir / "api" / "overview.json").exists())

    def test_api_token_pricing_json(self):
        self.assertTrue((self.site_dir / "api" / "token-pricing.json").exists())

    def test_api_business_json(self):
        self.assertTrue((self.site_dir / "api" / "business.json").exists())

    def test_api_gpu_pricing_json(self):
        self.assertTrue((self.site_dir / "api" / "gpu-pricing.json").exists())

    def test_api_health_json(self):
        self.assertTrue((self.site_dir / "api" / "health.json").exists())

    def test_second_phase_api_files(self):
        for name in ("supply-chain.json", "investment.json", "history.json"):
            self.assertTrue((self.site_dir / "api" / name).exists())

    # ── No CDN or hardcoded paths ──────────────────────────────
    def test_no_cdn_in_html(self):
        for html_file in self.site_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            self.assertNotIn("cdn.", content.lower(),
                f"{html_file.relative_to(self.site_dir)} 包含 CDN 引用")
            self.assertNotIn("https://fonts.googleapis.com", content)
            self.assertNotIn("https://unpkg.com", content)
            self.assertNotIn("https://cdn.jsdelivr.net", content)

    def test_no_absolute_paths_in_html(self):
        for html_file in self.site_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            self.assertNotIn("C:\\", content)
            self.assertNotIn("D:\\", content)
            self.assertNotIn("/Users/", content)
            self.assertNotIn("/home/", content)

    def test_no_hardcoded_domain_in_html(self):
        """HTML 中不应出现硬编码的 github.io 域名（应该用相对路径）。"""
        for html_file in self.site_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            # script/link 标签不应使用绝对 URL
            script_refs = re.findall(r'src="(https?://[^"]+)"', content)
            link_refs = re.findall(r'href="(https?://[^"]+)"', content)
            all_refs = script_refs + link_refs
            for ref in all_refs:
                self.assertTrue(
                    ref.startswith("https://github.com") or
                    ref.startswith("https://api.") or
                    ref.startswith("https://platform.") or
                    ref.startswith("https://help.") or
                    ref.startswith("https://www.") or
                    ref.startswith("https://developers.") or
                    ref.startswith("https://docs.") or
                    ref.startswith("https://finance.") or
                    ref.startswith("https://news.") or
                    ref.startswith("https://aws.") or
                    ref.startswith("https://bigmodel.") or
                    ref.startswith("https://cohere.") or
                    ref.startswith("https://mistral.") or
                    ref.startswith("https://x.ai") or
                    ref.startswith("https://arxiv."),
                    f"{html_file.relative_to(self.site_dir)} 含未知外部URL: {ref}"
                )


if __name__ == "__main__":
    unittest.main()
