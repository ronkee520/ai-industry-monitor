#!/usr/bin/env python3
"""AI Industry Monitor — 数据采集与构建编排器。

按顺序执行: 采集器 → 构建 dashboard → 构建站点。

用法:
    python scripts/run_all.py --project-root .
    python scripts/run_all.py --project-root . --skip-fetch --verbose
    python scripts/run_all.py --project-root . --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

# 延迟导入，确保路径正确
import scripts._shared as _shared  # noqa: E402
import scripts.collect_token_pricing as _token  # noqa: E402
import scripts.collect_gpu_pricing as _gpu  # noqa: E402
import scripts.collect_news as _news  # noqa: E402
import scripts.collect_business_metrics as _business  # noqa: E402
import scripts.build_dashboard as _dashboard  # noqa: E402
import scripts.build_site as _site  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Industry Monitor — 运行完整流水线")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--skip-fetch", action="store_true", help="跳过数据采集，仅构建")
    parser.add_argument("--dry-run", action="store_true", help="仅打印、不写入文件")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def run_all(
    root: Path,
    *,
    skip_fetch: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """编排执行完整流水线。"""
    started = time.time()
    results: dict[str, Any] = {"phases": {}}

    # ── Phase 1: 采集 ──
    if skip_fetch:
        print("[run_all] 跳过数据采集 (--skip-fetch)")
        results["phases"]["fetch"] = {"status": "skipped"}
    else:
        print("[run_all] Phase 1: 数据采集")
        for name, mod in [
            ("token_pricing", _token),
            ("gpu_pricing", _gpu),
            ("news", _news),
            ("business_metrics", _business),
        ]:
            label = f"collect_{name}"
            try:
                func = getattr(mod, f"collect_{name}")
                r = func(root, dry_run=dry_run, verbose=verbose)
                results["phases"][label] = r
                print(f"  {label}: {r.get('status', 'ok')}")
            except Exception as exc:
                results["phases"][label] = {"status": "error", "error": str(exc)}
                print(f"  {label}: ERROR — {exc}", file=sys.stderr)

    # ── Phase 2: 构建 Dashboard ──
    print("[run_all] Phase 2: 构建 Dashboard 数据")
    try:
        payload = _dashboard.build_dashboard(root, verbose=verbose)
        results["phases"]["build_dashboard"] = {"status": "ok",
            "pricing_count": len(payload.get("token_pricing", {}).get("records", [])),
            "business_count": len(payload.get("business", {}).get("records", []))}
        print(f"  dashboard: {results['phases']['build_dashboard']['pricing_count']} pricing + "
              f"{results['phases']['build_dashboard']['business_count']} business records")
    except Exception as exc:
        results["phases"]["build_dashboard"] = {"status": "error", "error": str(exc)}
        print(f"  dashboard: ERROR — {exc}", file=sys.stderr)

    # ── Phase 3: 构建站点 ──
    print("[run_all] Phase 3: 构建静态站点")
    try:
        site_dir = _site.build_site(root, verbose=verbose)
        results["phases"]["build_site"] = {"status": "ok", "path": str(site_dir)}
        print(f"  site: {site_dir}")
    except Exception as exc:
        results["phases"]["build_site"] = {"status": "error", "error": str(exc)}
        print(f"  site: ERROR — {exc}", file=sys.stderr)

    elapsed = round(time.time() - started, 1)
    results["elapsed_seconds"] = elapsed
    print(f"[run_all] 完成 ({elapsed}s)")

    return results


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = run_all(
        root,
        skip_fetch=args.skip_fetch,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    # 检查是否有致命错误
    errors = sum(
        1 for v in result.get("phases", {}).values()
        if isinstance(v, dict) and v.get("status") == "error"
    )
    return min(errors, 1)


if __name__ == "__main__":
    raise SystemExit(main())
