#!/usr/bin/env python3
"""AI Industry Monitor — Token 定价采集器。

从各公司官方定价页抓取 HTML，计算内容指纹，检测页面变化。
对结构稳定的页面尝试提取可见文本；解析失败时回退到 manual fallback。

单独运行:
    python scripts/collect_token_pricing.py --project-root .
    python scripts/collect_token_pricing.py --project-root . --dry-run --verbose
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path
from typing import Any

# ── 项目路径 ──
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Token 定价采集器")
    parser.add_argument("--project-root", default=None, help="项目根目录（默认自动推导）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要执行的操作，不写入文件")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    return parser.parse_args()


def log(message: str, *, verbose: bool = False, force: bool = False) -> None:
    """条件日志输出。"""
    if force or verbose:
        print(f"[token_pricing] {message}")


def collect_token_pricing(
    root: Path, *, dry_run: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """主采集逻辑。

    1. 读取 config/sources.json 中的 pricing_sources
    2. 并发 fetch 每个定价页
    3. 与上次 source_state 比较 content_hash，标记 changed
    4. 写入 source_state.json
    5. 返回采集摘要
    """
    sources_cfg = _shared.load_json(root / "config" / "sources.json", {})
    pricing_sources: list[dict[str, Any]] = sources_cfg.get("pricing_sources", [])
    if not pricing_sources:
        log("未找到定价页配置，跳过", force=True)
        return {"status": "skipped", "reason": "no_sources_configured", "fetched": 0}

    # 读取上次状态
    prev_state_path = root / "data" / "automated" / "source_state.json"
    prev_state = _shared.load_json(prev_state_path, [])
    prev_by_id: dict[str, dict[str, Any]] = {
        item["source_id"]: item for item in prev_state if "source_id" in item
    }

    # dry-run 模式：不访问网络，仅返回计划摘要
    if dry_run:
        log(f"[DRY-RUN] 将采集 {len(pricing_sources)} 个来源（不访问网络）", force=True)
        return {
            "collector": "token_pricing",
            "total": len(pricing_sources),
            "fetched": 0,
            "ok": 0,
            "changed": 0,
            "errors": 0,
            "dry_run": True,
            "planned_sources": [s["id"] for s in pricing_sources if s.get("enabled", True)],
        }

    source_states: list[dict[str, Any]] = []
    ok_count = 0
    changed_count = 0
    error_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_map: dict[concurrent.futures.Future, dict[str, Any]] = {}
        for source in pricing_sources:
            if not source.get("enabled", True):
                continue
            future_map[executor.submit(_fetch_source, source, prev_by_id)] = source

        for future in concurrent.futures.as_completed(future_map):
            source = future_map[future]
            try:
                state = future.result()
            except Exception as exc:
                state = _error_state(source, f"{type(exc).__name__}: {exc}")
            source_states.append(state)

            if state.get("status") == "ok":
                ok_count += 1
                if state.get("changed"):
                    changed_count += 1
            else:
                error_count += 1

            log(
                f"来源 {source['id']}: status={state.get('status')} "
                f"changed={state.get('changed')} chars={state.get('text_chars', 0)}",
                verbose=verbose,
            )

    # 按配置顺序排序
    order = {src["id"]: i for i, src in enumerate(pricing_sources)}
    source_states.sort(key=lambda x: order.get(x.get("source_id", ""), 999))

    summary = {
        "collector": "token_pricing",
        "total": len(pricing_sources),
        "fetched": len(source_states),
        "ok": ok_count,
        "changed": changed_count,
        "errors": error_count,
    }

    # dry_run 已在上方提前返回
    _shared.atomic_write(prev_state_path, source_states)
    log(f"source_state.json 已写入 ({len(source_states)} 条)", force=True)

    return summary


def _fetch_source(
    source: dict[str, Any], prev_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """抓取单个定价源，返回状态记录。"""
    prev = prev_by_id.get(source["id"], {})
    result = _shared.fetch_url(source["url"])
    checked_at = _shared.now_shanghai().isoformat(timespec="seconds")

    state: dict[str, Any] = {
        "source_id": source["id"],
        "company_id": source.get("company_id"),
        "kind": source.get("kind"),
        "name": source.get("name", source["id"]),
        "url": source["url"],
        "checked_at": checked_at,
        "status": "error",
        "http_status": None,
        "final_url": None,
        "content_hash": None,
        "changed": None,
        "text_chars": None,
        "error": None,
    }

    if result["ok"]:
        text = result["text"] or ""
        digest = result["content_hash"]
        old_hash = prev.get("content_hash")
        is_changed = (
            bool(old_hash and old_hash != digest) if digest else None
        )

        state.update({
            "status": "ok" if result["text_chars"] and result["text_chars"] >= 100
                      else "partial_dynamic",
            "http_status": result["status"],
            "final_url": result["final_url"],
            "content_hash": digest,
            "changed": is_changed,
            "text_chars": result["text_chars"],
            "error": None if result["text_chars"] and result["text_chars"] >= 100
                     else "页面主要内容可能由前端动态加载，可见文本过少",
        })
    else:
        state["error"] = result.get("error", "unknown")

    return state


def _error_state(source: dict[str, Any], error: str) -> dict[str, Any]:
    """生成错误状态记录。"""
    return {
        "source_id": source["id"],
        "company_id": source.get("company_id"),
        "kind": source.get("kind"),
        "name": source.get("name", source["id"]),
        "url": source["url"],
        "checked_at": _shared.now_shanghai().isoformat(timespec="seconds"),
        "status": "error",
        "http_status": None,
        "final_url": None,
        "content_hash": None,
        "changed": None,
        "text_chars": None,
        "error": error[:400],
    }


# ── main ──────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = collect_token_pricing(root, dry_run=args.dry_run, verbose=args.verbose)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("errors", 0) < len(
        _shared.load_json(root / "config" / "sources.json", {}).get("pricing_sources", [])
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
