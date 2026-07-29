#!/usr/bin/env python3
"""AI Industry Monitor — 人工定价数据导入器。

读取 manual_pricing_template.csv，根据填写的价格更新 token_pricing.json。

公式: blended_cost = input × 0.65 + output × 0.35

用法:
    python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv --dry-run
    python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="人工定价数据导入器")
    parser.add_argument("--project-root", default=None, help="项目根目录")
    parser.add_argument("--template", required=True, help="CSV 模板路径（相对于 project-root 或绝对路径）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览变更，不写入文件")
    return parser.parse_args()


def load_template(path: Path) -> list[dict[str, str]]:
    """读取 CSV 模板，返回 list[dict]。"""
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("模板为空，请至少填写一行数据。")

    required = {"company_id", "model_id", "input_price_per_m", "output_price_per_m"}
    header = set(rows[0].keys())
    missing = required - header
    if missing:
        raise ValueError(f"CSV 模板缺少必需列: {missing}")

    return rows


def update_pricing(
    root: Path, template_path: str, *, dry_run: bool = False
) -> dict[str, Any]:
    """主逻辑：读 CSV → 更新 token_pricing.json。"""
    tmpl_path = _resolve_template(root, template_path)
    tmpl_rows = load_template(tmpl_path)

    pricing_path = root / "data" / "manual" / "token_pricing.json"
    pricing_data = _shared.load_json(pricing_path, {})
    records: list[dict[str, Any]] = pricing_data.get("records", [])

    today_str = date.today().isoformat()
    update_key = lambda r: f"{r.get('company_id','')}::{r.get('model_id','')}"

    # 建立索引
    record_index: dict[str, dict[str, Any]] = {update_key(r): r for r in records}

    updated: list[str] = []
    skipped: list[str] = []
    unchanged: list[str] = []

    for row in tmpl_rows:
        cid = row.get("company_id", "").strip()
        mid = row.get("model_id", "").strip()
        key = f"{cid}::{mid}"

        inp_str = (row.get("input_price_per_m") or "").strip()
        out_str = (row.get("output_price_per_m") or "").strip()
        cached_str = (row.get("cached_input_price_per_m") or "").strip()
        currency = (row.get("currency") or "USD").strip()
        tier = (row.get("tier") or "standard").strip()

        if not inp_str or not out_str:
            skipped.append(key)
            continue

        try:
            inp = float(inp_str.replace(",", ""))
            outp = float(out_str.replace(",", ""))
        except ValueError as e:
            print(f"[WARNING] {key}: 无法解析价格 — {e}", file=sys.stderr)
            skipped.append(key)
            continue

        cached = None
        if cached_str:
            try:
                cached = float(cached_str.replace(",", ""))
            except ValueError:
                pass

        blended = _shared.blended_cost(inp, outp, input_weight=0.65, output_weight=0.35)

        if key in record_index:
            rec = record_index[key]
        else:
            # 模型不在现有 records 中，追加新记录
            rec = _make_new_record(cid, mid, row, currency, tier)
            records.append(rec)
            record_index[key] = rec

        # 更新字段
        rec["input_per_m"] = inp
        rec["output_per_m"] = outp
        rec["cached_input_per_m"] = cached
        rec["value"] = blended
        rec["currency"] = currency
        rec["tier"] = tier
        rec["as_of_date"] = today_str
        rec["period"] = today_str[:7]  # YYYY-MM
        rec["collected_at"] = _shared.now_shanghai().isoformat(timespec="seconds")
        rec["source_tier"] = 1
        rec["evidence_status"] = "official_pricing"
        rec["confidence"] = "verified"

        source_name = (row.get("source_name") or "").strip()
        note_extra = (row.get("note") or "").strip()
        rec["source_name"] = source_name or rec.get("source_name", "")

        base_note = f"manual entry from official pricing page, checked on {today_str}"
        if note_extra:
            base_note += f". {note_extra}"
        rec["note"] = base_note

        # 更新 tags
        tags: list[str] = rec.get("tags") or []
        for tag in ("verified", "manual_entry", "official_pricing"):
            if tag not in tags:
                tags.append(tag)
        # 移除旧标记
        for stale in ("manual_required", "sample", "missing"):
            if stale in tags:
                tags.remove(stale)
        rec["tags"] = tags

        updated.append(key)

    # 标记 CSV 中未填价格的记录为 manual_required
    for key, rec in record_index.items():
        if key not in updated:
            if rec.get("confidence") == "manual_required":
                unchanged.append(key)

    summary = {
        "updated": len(updated),
        "skipped": len(skipped),
        "unchanged": len(unchanged),
        "total_records": len(records),
        "updated_keys": updated,
        "skipped_keys": skipped,
    }

    if dry_run:
        print(f"[DRY-RUN] 将更新 {len(updated)} 条，跳过 {len(skipped)} 条（未填价格）")
        for k in updated:
            rec = record_index[k]
            print(f"  [UPDATE] {k}: input={rec['input_per_m']}, output={rec['output_per_m']}, blended={rec['value']}, confidence={rec['confidence']}")
        for k in skipped:
            print(f"  [SKIP]   {k}: 未填写 input/output 价格，保持 manual_required")
        return summary

    # 写入
    pricing_data["records"] = records
    pricing_data["_last_updated"] = today_str
    _shared.atomic_write(pricing_path, pricing_data)
    print(f"[OK] 已写入 {pricing_path} ({len(updated)} 条 verified, {len(skipped)} 条保持 manual_required)")
    return summary


def _make_new_record(
    cid: str, mid: str, row: dict[str, str], currency: str, tier: str
) -> dict[str, Any]:
    """为 CSV 中有但 token_pricing.json 中没有的模型创建新记录。"""
    company_name = (row.get("company_name") or cid).strip()
    model_name = (row.get("model_name") or mid).strip()
    return {
        "metric_id": f"token_blended_cost::{cid}::{mid}::{tier}",
        "metric_name": f"{model_name} 标准档混合成本",
        "metric_category": "token_pricing",
        "value": None,
        "input_per_m": None,
        "output_per_m": None,
        "cached_input_per_m": None,
        "unit": "USD_per_1M_tokens" if currency.upper() == "USD" else "CNY_per_1M_tokens",
        "currency": currency,
        "company_id": cid,
        "model_id": mid,
        "region": "overseas",
        "tier": tier,
        "period": "",
        "as_of_date": "",
        "collected_at": "",
        "source_name": (row.get("source_name") or "").strip(),
        "source_url": (row.get("source_url") or "").strip(),
        "source_tier": 1,
        "evidence_status": "manual_required",
        "confidence": "manual_required",
        "note": "",
        "tags": ["manual_required", "blended"],
    }


def _resolve_template(root: Path, path_str: str) -> Path:
    """解析模板路径。支持相对路径（相对于 project-root）和绝对路径。"""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (root / p).resolve()


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = update_pricing(root, args.template, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
