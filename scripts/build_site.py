#!/usr/bin/env python3
"""AI Industry Monitor — 静态站点构建器。

读取 data/automated/dashboard.json，生成 _site/ 多路径站点。

输出:
    _site/index.html                  — 首页（总览/AI Cycle）
    _site/token/index.html            — Token 经济
    _site/business/index.html         — 商业化
    _site/compute/index.html          — AI算力 & 云CAPEX
    _site/methodology/index.html      — 方法论与数据
    _site/app.js styles.css favicon.svg — 静态资源
    _site/.nojekyll                   — 禁用 Jekyll
    _site/api/*.json                  — 7 个 JSON API 端点

单独运行:
    python scripts/build_site.py --project-root .
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402

# 子页面定义：目录名 → 用于构建的相对前缀
SUB_PAGES = {
    "token":        "../",
    "business":     "../",
    "compute":      "../",
    "methodology":  "../",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建静态站点")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def build_site(root: Path, *, verbose: bool = False) -> Path:
    """构建 _site/ 目录，生成首页 + 4 个子页面 + 7 个 API 端点。"""
    site_dir = root / "_site"

    # 清理旧构建
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)

    # 加载数据
    dashboard = _shared.load_json(root / "data" / "automated" / "dashboard.json", {})
    dashboard_v1 = _shared.load_json(root / "data" / "automated" / "dashboard_v1.json", {})
    health = _shared.load_json(root / "data" / "automated" / "health.json", {})

    if not dashboard:
        dashboard = dashboard_v1
    if not dashboard:
        dashboard = _placeholder_dashboard()
    if not health:
        health = {"status": "no_data", "generated_at": _shared.now_shanghai().isoformat()}

    # ── 复制静态资源到 _site/ 根目录 ──
    web_dir = root / "web"
    for name in ("app.js", "styles.css", "favicon.svg"):
        src = web_dir / name
        if src.exists():
            shutil.copy2(src, site_dir / name)
            if verbose:
                print(f"  复制 {name} → _site/")

    # ── 读取 HTML 模板 ──
    template_path = web_dir / "index.html"
    if not template_path.exists():
        _write_placeholder(site_dir, dashboard)
        _write_api(site_dir, dashboard, health, verbose)
        return site_dir

    template = template_path.read_text(encoding="utf-8")

    # ── 渲染函数：替换模板变量 ──
    def render_page(root_prefix: str, asset_prefix: str) -> str:
        return (
            template
            .replace("{{ROOT_PREFIX}}", root_prefix)
            .replace("{{ASSET_PREFIX}}", asset_prefix)
        )

    # ── 首页：ROOT=./  ASSET=./  ──
    home_html = render_page("./", "./")
    (site_dir / "index.html").write_text(home_html, encoding="utf-8")
    if verbose:
        print("  生成 index.html (ROOT=./)")

    # ── 子页面：ROOT=../  ASSET=../  ──
    for sub_dir in SUB_PAGES:
        sub_path = site_dir / sub_dir
        sub_path.mkdir(parents=True, exist_ok=True)
        sub_html = render_page("../", "../")
        (sub_path / "index.html").write_text(sub_html, encoding="utf-8")
        if verbose:
            print(f"  生成 {sub_dir}/index.html (ROOT=../)")

    # ── .nojekyll ──
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    # ── API ──
    _write_api(site_dir, dashboard, health, verbose)

    # ── 构建后校验 ──
    _verify_build(site_dir)
    if verbose:
        print(f"_site/ 构建完成 ({len(SUB_PAGES) + 1} HTML 页面 + API)")

    return site_dir


def _write_api(site_dir: Path, dashboard: dict[str, Any], health: dict[str, Any], verbose: bool) -> None:
    """写入所有 JSON API 端点。"""
    api_dir = site_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    meta = dashboard.get("meta", {})

    endpoints: dict[str, Any] = {
        "dashboard.json":      dashboard,
        "overview.json":       {"meta": meta, "overview": dashboard.get("overview", {}), "health": health},
        "token-pricing.json":  {"meta": meta, **dashboard.get("token_pricing", {})},
        "business.json":       {"meta": meta, **dashboard.get("business", {})},
        "gpu-pricing.json":    {"meta": meta, **dashboard.get("compute", {})},
        "health.json":         health,
    }

    for filename, data in endpoints.items():
        _shared.atomic_write(api_dir / filename, data)

    api_index = {
        "name": "AI Industry Monitor API",
        "version": "1.0.0",
        "snapshot_at": meta.get("generated_at", ""),
        "refresh_schedule": "每周一、周五 09:00 (Asia/Shanghai)",
        "endpoints": [
            {"path": "./dashboard.json",     "description": "全量快照（所有模块）"},
            {"path": "./overview.json",      "description": "总览 + AI Cycle 评分 + 健康"},
            {"path": "./token-pricing.json", "description": "Token 定价数据"},
            {"path": "./business.json",      "description": "商业化指标（ARR/收入/融资）"},
            {"path": "./gpu-pricing.json",   "description": "GPU 定价 + CAPEX"},
            {"path": "./health.json",        "description": "系统健康报告"},
        ],
        "note": "GitHub Pages 静态 JSON。sample/missing 数据均有明确标记。",
    }
    _shared.atomic_write(api_dir / "index.json", api_index)
    if verbose:
        print(f"  写入 {len(endpoints) + 1} API 文件")


def _verify_build(site_dir: Path) -> None:
    """构建后校验：确保无残留模板变量。"""
    import re
    for html_file in site_dir.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        for placeholder in ("{{ROOT_PREFIX}}", "{{ASSET_PREFIX}}"):
            if placeholder in content:
                raise RuntimeError(
                    f"构建校验失败: {html_file.relative_to(site_dir)} 中残留未替换的 {placeholder}"
                )
        # 确保 DASHBOARD_ROOT 被正确设置
        if "{{ROOT_PREFIX}}" not in content and "{{ASSET_PREFIX}}" not in content:
            continue  # 已通过


def _write_placeholder(site_dir: Path, dashboard: dict[str, Any]) -> None:
    """写入最小占位 HTML（web/ 目录不存在时的 fallback）。"""
    meta = dashboard.get("meta", {})
    cycle = dashboard.get("overview", {}).get("cycle", {})
    html = f"""<!doctype html><html lang="zh-CN">
<head><meta charset="utf-8"><title>AI Industry Monitor</title>
<style>body{{font-family:system-ui;max-width:900px;margin:40px auto;padding:20px;color:#1e293b;background:#f8fafc}}h1{{color:#2563eb}}.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:16px 0}}</style></head>
<body><h1>🔵 AI Industry Monitor</h1><p>生成时间: {meta.get('generated_at','—')}</p>
<div class="card"><h2>产业阶段: {cycle.get('stage_label','—')}</h2><p>请运行 python scripts/run_all.py 更新数据。</p></div>
<p>📡 <a href="./api/index.json">API 目录</a></p></body></html>"""
    (site_dir / "index.html").write_text(html, encoding="utf-8")


def _placeholder_dashboard() -> dict[str, Any]:
    now = _shared.now_shanghai().isoformat(timespec="seconds")
    return {
        "meta": {"title": "AI Industry Monitor", "generated_at": now, "schedule": "每周一、周五 09:00"},
        "kpis": {"companies": 21, "models_with_pricing": 0, "source_ok": 0, "source_total": 0, "arr_disclosures": 0},
        "overview": {"cycle": {"stage_label": "数据不足", "industry_development_score": None, "risk_crowding_score": None, "confidence": "missing", "missing_factor_count": 3}},
        "token_pricing": {"records": []}, "business": {"records": []}, "compute": {"gpu": []},
        "health": {"status": "no_data", "sources_ok": 0, "sources_total": 0},
    }


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    build_site(root, verbose=args.verbose)
    print(f"[build_site] 完成 → {root / '_site'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
