#!/usr/bin/env python3
"""AI Industry Monitor — 商业化指标采集器。

第一期不自动从新闻中提取数字。此脚本负责：
1. 读取 data/manual/business_metrics.json
2. 检查每条的 freshness 和完整性
3. 输出 health 相关状态

单独运行:
    python scripts/collect_business_metrics.py --project-root .
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="商业化指标采集器")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def log(msg: str, *, force: bool = False, verbose: bool = False) -> None:
    if force or verbose:
        print(f"[business] {msg}")


def collect_business_metrics(
    root: Path, *, dry_run: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """读取 manual 数据并生成 status 报告。"""
    manual_path = root / "data" / "manual" / "business_metrics.json"
    data = _shared.load_json(manual_path, {})
    records: list[dict[str, Any]] = data.get("records", [])

    now = _shared.now_shanghai()
    stats = {
        "total": 0,
        "has_value": 0,
        "missing": 0,
        "sample": 0,
        "verified": 0,
        "fresh": 0,
        "stale": 0,
    }

    for rec in records:
        stats["total"] += 1
        val = rec.get("value")
        if val is None:
            stats["missing"] += 1
        else:
            stats["has_value"] += 1

        conf = rec.get("confidence", "missing")
        if conf == "sample":
            stats["sample"] += 1
        elif conf == "verified":
            stats["verified"] += 1

        fresh = _shared.freshness(rec.get("as_of_date"), today=now.date())
        if fresh["status"] == "fresh":
            stats["fresh"] += 1
        elif fresh["status"] in ("stale", "very_stale"):
            stats["stale"] += 1

    summary: dict[str, Any] = {
        "collector": "business_metrics",
        "source": "data/manual/business_metrics.json",
        "mode": "manual_only",
        "stats": stats,
    }
    log(json.dumps(summary, ensure_ascii=False, indent=2), force=True)
    return summary


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    collect_business_metrics(root, dry_run=args.dry_run, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
