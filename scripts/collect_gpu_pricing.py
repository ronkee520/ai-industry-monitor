#!/usr/bin/env python3
"""AI Industry Monitor — GPU 定价采集器。

从 RunPod / Vast.ai / 阿里云等公开 GPU 租赁页面获取当前状态。
记录 source_state（状态指纹），并对结构稳定的数据源解析标准化价格。
解析失败时保留上一份自动化快照。

单独运行:
    python scripts/collect_gpu_pricing.py --project-root .
    python scripts/collect_gpu_pricing.py --project-root . --dry-run --verbose
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
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
    parsed_records: list[dict[str, Any]] = []
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
            if r.get("ok") and src.get("parser") == "lambda_price_table":
                parsed_records.extend(_parse_lambda_pricing(src, r.get("text", "")))
            if r.get("ok") and src.get("parser") == "runpod_price_table":
                parsed_records.extend(_parse_runpod_pricing(src, r.get("text", "")))
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
    snapshot_path = root / "data" / "automated" / "gpu_pricing.json"
    previous_snapshot = _shared.load_json(snapshot_path, {})
    if parsed_records:
        _shared.atomic_write(snapshot_path, {
            "generated_at": _shared.now_shanghai().isoformat(timespec="seconds"),
            "records": parsed_records,
        })
    elif previous_snapshot:
        parsed_records = previous_snapshot.get("records", [])
    log("source_state.json 已更新（含GPU条目）", force=True)
    summary: dict[str, Any] = {
        "collector": "gpu_pricing",
        "total": len(gpu_sources),
        "fetched": len(gpu_states),
        "ok": ok,
        "errors": err,
        "records": len(parsed_records),
        "status": "ok" if err == 0 else "partial",
    }
    return summary


def _parse_lambda_pricing(src: dict[str, Any], html: str) -> list[dict[str, Any]]:
    """Extract the minimum displayed per-GPU hourly price for each Lambda SKU."""
    text = _shared.visible_text(html)
    names = [
        ("B200 SXM6", 180), ("H100 SXM", 80), ("H100 PCIe", 80),
        ("GH200", 96), ("A100 SXM", None), ("A100 PCIe", None),
        ("A10", 24), ("A6000", 48), ("Tesla V100", 16), ("Quadro RTX 6000", 24),
    ]
    now = _shared.now_shanghai().isoformat(timespec="seconds")
    today = now[:10]
    out: list[dict[str, Any]] = []
    for name, default_vram in names:
        pattern = re.compile(rf"NVIDIA\s+{re.escape(name)}\s*(?:\|)?\s*(\d+)\s*GB.{{0,220}}?\$\s*([0-9]+(?:\.[0-9]+)?)", re.I)
        matches = pattern.findall(text)
        if not matches:
            continue
        prices = [float(price) for _, price in matches]
        vrams = [int(vram) for vram, _ in matches]
        value = min(prices)
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        out.append({
            "metric_id": f"gpu_rental_hourly::lambda::{slug}::ondemand_min",
            "metric_name": f"Lambda {name} 按需最低展示价", "metric_category": "gpu_pricing",
            "value": value, "unit": "USD_per_GPU_hour", "currency": "USD", "company_id": None,
            "provider": src.get("provider", "Lambda Cloud"), "gpu_model": f"NVIDIA {name}",
            "vram_gb": max(vrams) if vrams else default_vram, "price_type": "on_demand_displayed_min",
            "region": "global", "period": today, "as_of_date": today, "collected_at": now,
            "source_name": src.get("name"), "source_url": src.get("url"), "source_tier": src.get("tier", 1),
            "evidence_status": "official_pricing", "confidence": "verified",
            "note": "取官方页面不同实例规模中展示的每GPU小时最低价；不含税，不代表任一区域实时可用性。",
            "tags": ["automated", "official", "on_demand"]
        })
    return out


def _parse_runpod_pricing(src: dict[str, Any], html: str) -> list[dict[str, Any]]:
    """Extract RunPod public Pods prices, normalized to USD/GPU-hour.

    The official page also lists Serverless and cluster prices.  For each GPU
    we retain the lowest public hourly price found on the page and identify the
    record explicitly as a displayed minimum, so it is not mistaken for a
    region-specific guaranteed quote.
    """
    text = _shared.visible_text(html)
    # RunPod 页面同时包含 Pods、Serverless 与 Clusters；本看板只比较
    # Pods 的单卡按小时价格，避免把另一产品线的价格串入同名 GPU。
    pods_start = text.find("Thousands of GPUs across")
    pods_end = text.find("Serverless", pods_start if pods_start >= 0 else 0)
    if pods_start >= 0 and pods_end > pods_start:
        text = text[pods_start:pods_end]
    names = [
        ("B300", 288), ("B200", 180), ("H200", 141),
        ("RTX Pro 6000", 96), ("H100 NVL", 94), ("H100 PCIe", 80),
        ("H100 SXM", 80), ("A100 PCIe", 80), ("A100 SXM", 80),
        ("Pro 6000 MIG 48GB", 48), ("L40S", 48), ("RTX 6000 Ada", 48),
        ("A40", 48), ("L40", 48),
        ("RTX A6000", 48), ("RTX 5090", 32), ("L4", 24),
        ("Pro 6000 MIG 24GB", 24), ("RTX 3090", 24),
        ("RTX 4090", 24), ("RTX A5000", 24),
    ]
    now = _shared.now_shanghai().isoformat(timespec="seconds")
    today = now[:10]
    out: list[dict[str, Any]] = []
    model_pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:" + "|".join(
            re.escape(name) for name, _ in sorted(names, key=lambda item: len(item[0]), reverse=True)
        ) + r")(?![A-Za-z0-9])",
        re.I,
    )
    for name, vram in names:
        prices: list[float] = []
        name_pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", re.I
        )
        for match in name_pattern.finditer(text):
            next_model = model_pattern.search(text, match.end())
            block_end = min(next_model.start() if next_model else len(text), match.end() + 520)
            block = text[match.end():block_end]
            prices.extend(
                float(value)
                for value in re.findall(r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*/?\s*(?:hr|hour)", block, re.I)
            )
        if not prices:
            continue
        value = min(prices)
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        out.append({
            "metric_id": f"gpu_rental_hourly::runpod::{slug}::ondemand_min",
            "metric_name": f"RunPod {name} 按需最低展示价",
            "metric_category": "gpu_pricing",
            "value": value, "unit": "USD_per_GPU_hour", "currency": "USD",
            "company_id": None, "provider": src.get("provider", "RunPod"),
            "gpu_model": f"NVIDIA {name}", "vram_gb": vram,
            "price_type": "on_demand_displayed_min", "region": "global",
            "period": today, "as_of_date": today, "collected_at": now,
            "source_name": src.get("name"), "source_url": src.get("url"),
            "source_tier": src.get("tier", 1),
            "evidence_status": "official_pricing", "confidence": "verified",
            "note": "取RunPod官方Pods页面公开展示的每GPU小时最低价；不同区域、安全云/社区云、实时库存和税费可能不同。",
            "tags": ["automated", "official", "on_demand", "displayed_min"],
        })
    return out


def _gpu_state(
    src: dict[str, Any], result: dict[str, Any], prev: dict[str, Any]
) -> dict[str, Any]:
    checked = _shared.now_shanghai().isoformat(timespec="seconds")
    ok = result.get("ok", False)
    text = result.get("text", "")
    digest = _shared.hash_content(text) if text else None
    old = prev.get("content_hash")
    state = {
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
    if not ok and prev.get("content_hash"):
        state.update({
            "status": "stale_fallback",
            "http_status": prev.get("http_status"),
            "final_url": prev.get("final_url"),
            "content_hash": prev.get("content_hash"),
            "changed": None,
            "text_chars": prev.get("text_chars"),
            "last_successful_check": prev.get("last_successful_check") or prev.get("checked_at"),
        })
    elif ok:
        state["last_successful_check"] = checked
    return state


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = collect_gpu_pricing(root, dry_run=args.dry_run, verbose=args.verbose)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
