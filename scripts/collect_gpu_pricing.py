#!/usr/bin/env python3
"""AI Industry Monitor — GPU 定价采集器。

从 RunPod / Vast.ai / 阿里云等公开 GPU 租赁页面获取当前状态。
第一版只记录 source_state（状态指纹），不尝试精确解析价格。
解析失败时回退到 data/manual/ 中的手动维护数据。

单独运行:
    python scripts/collect_gpu_pricing.py --project-root .
    python scripts/collect_gpu_pricing.py --project-root . --dry-run --verbose
"""

from __future__ import annotations

import argparse
import concurrent.futures
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
    parser = argparse.ArgumentParser(description="GPU 定价采集器")
    parser.add_argument("--project-root", default=None, help="项目根目录")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def log(msg: str, *, verbose: bool = False, force: bool = False) -> None:
    if force or verbose:
        print(f"[gpu_pricing] {msg}")


def collect_gpu_pricing(
    root: Path, *, dry_run: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """抓取 GPU 定价源的状态指纹。"""
    sources_cfg = _shared.load_json(root / "config" / "sources.json", {})
    gpu_sources: list[dict[str, Any]] = sources_cfg.get("gpu_sources", [])
    if not gpu_sources:
        log("未找到 GPU 源配置，跳过", force=True)
        return {"status": "skipped", "reason": "no_gpu_sources", "fetched": 0}

    # dry-run 模式：不访问网络
    if dry_run:
        log(f"[DRY-RUN] 将采集 {len(gpu_sources)} 个 GPU 来源（不访问网络）", force=True)
        return {
            "collector": "gpu_pricing", "total": len(gpu_sources),
            "ok": 0, "errors": 0, "dry_run": True,
            "planned_sources": [s["id"] for s in gpu_sources if s.get("enabled", True)],
        }

    # 读取现有 source_state（可能含 token 采集器的结果），仅更新 GPU 部分
    state_path = root / "data" / "automated" / "source_state.json"
    existing = _shared.load_json(state_path, [])
    existing_by_id: dict[str, dict[str, Any]] = {
        item["source_id"]: item for item in existing if "source_id" in item
    }

    gpu_states: list[dict[str, Any]] = []
    ok = err = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_shared.fetch_url, s["url"]): s for s in gpu_sources if s.get("enabled", True)}
        for fut in concurrent.futures.as_completed(futs):
            src = futs[fut]
            try:
                r = fut.result()
            except Exception as exc:
                r = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

            state = _gpu_state(src, r, existing_by_id.get(src["id"], {}))
            gpu_states.append(state)
            if state["status"] == "ok":
                ok += 1
            else:
                err += 1
            log(f"GPU {src['id']}: {state['status']} chars={state.get('text_chars',0)}", verbose=verbose)

    # 合并回 source_state（保留非 GPU 条目）
    gpu_ids = {s["id"] for s in gpu_sources}
    merged = [item for item in existing if item.get("source_id") not in gpu_ids]
    merged.extend(gpu_states)

    # dry_run 已在上方提前返回，此处必然是 dry_run=False
    _shared.atomic_write(state_path, merged)
    log("source_state.json 已更新（含GPU条目）", force=True)
    return summary


def _gpu_state(
    src: dict[str, Any], result: dict[str, Any], prev: dict[str, Any]
) -> dict[str, Any]:
    checked = _shared.now_shanghai().isoformat(timespec="seconds")
    ok = result.get("ok", False)
    text = result.get("text", "")
    digest = _shared.hash_content(text) if text else None
    old = prev.get("content_hash")
    return {
        "source_id": src["id"],
        "provider": src.get("provider", ""),
        "kind": src.get("kind"),
        "name": src.get("name", src["id"]),
        "url": src["url"],
        "checked_at": checked,
        "status": "ok" if ok else "error",
        "http_status": result.get("status"),
        "final_url": result.get("final_url"),
        "content_hash": digest,
        "changed": bool(old and old != digest) if old and digest else None,
        "text_chars": len(text) if text else None,
        "error": result.get("error"),
    }


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = collect_gpu_pricing(root, dry_run=args.dry_run, verbose=args.verbose)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
