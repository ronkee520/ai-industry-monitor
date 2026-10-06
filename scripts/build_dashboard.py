#!/usr/bin/env python3
"""AI Industry Monitor — Dashboard 数据构建器。

合并 config + manual + automated 数据，输出统一快照。

输出:
    data/automated/dashboard.json     — 全量数据快照
    data/automated/health.json        — 系统健康报告
    data/automated/cycle_scores.json  — AI Cycle 评分

历史追加:
    data/history/token_pricing.jsonl
    data/history/business.jsonl
    data/history/gpu_pricing.jsonl
    data/history/cycle_scores.jsonl

单独运行:
    python scripts/build_dashboard.py --project-root .
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


def _expand_official_price_events(events: list[dict[str, Any]], through: date) -> list[dict[str, Any]]:
    """Expand verified effective-price events into daily validity intervals."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") == "official_price_effective" and event.get("date") and event.get("metric_id"):
            grouped.setdefault(event["metric_id"], []).append(event)
        else:
            passthrough.append(event)

    expanded = list(passthrough)
    for metric_id, metric_events in grouped.items():
        ordered = sorted(metric_events, key=lambda row: row["date"])
        for index, event in enumerate(ordered):
            start = date.fromisoformat(event["date"])
            next_start = date.fromisoformat(ordered[index + 1]["date"]) if index + 1 < len(ordered) else through + timedelta(days=1)
            end = min(through, next_start - timedelta(days=1))
            cursor = start
            while cursor <= end:
                row = dict(event)
                row["date"] = cursor.isoformat()
                if cursor != start:
                    row["event_type"] = "official_price_interval"
                    row["note"] = "官方生效价格在下一次已核验调价前持续有效。"
                expanded.append(row)
                cursor += timedelta(days=1)
    return expanded


# ── CLI ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 Dashboard 数据快照")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


# ── 主入口 ────────────────────────────────────────────────────────

def build_dashboard(root: Path, *, verbose: bool = False) -> dict[str, Any]:
    """读取所有数据源，合并为统一快照。"""
    now = _shared.now_shanghai()
    generated_at = now.isoformat(timespec="seconds")
    today = now.date()

    # 加载配置
    companies_cfg = _shared.load_json(root / "config" / "companies.json", {})
    models_cfg = _shared.load_json(root / "config" / "models.json", {})
    sources_cfg = _shared.load_json(root / "config" / "sources.json", {})
    cycle_cfg = _shared.load_json(root / "config" / "cycle_factors.json", {})
    fx = (companies_cfg.get("fx") or {}).get("cny_per_usd", 7.25)

    companies_list: list[dict[str, Any]] = companies_cfg.get("companies", [])
    models_list: list[dict[str, Any]] = models_cfg.get("models", [])
    company_by_id = {c["id"]: c for c in companies_list}
    model_by_id = {m["id"]: m for m in models_list}

    # 加载数据
    manual_pricing = _shared.load_json(root / "data" / "manual" / "token_pricing.json", {})
    manual_business = _shared.load_json(root / "data" / "manual" / "business_metrics.json", {})
    manual_supply = _shared.load_json(root / "data" / "manual" / "supply_chain_finance.json", {})
    market_pricing = _shared.load_json(root / "data" / "automated" / "model_market_pricing.json", {})
    market_price_history = _shared.load_json(
        root / "data" / "automated" / "model_market_price_history.json", {}
    ).get("records", [])
    sec_fundamentals = _shared.load_json(root / "data" / "automated" / "sec_fundamentals.json", {})
    market_snapshot = _shared.load_json(root / "data" / "automated" / "market.json", {})
    source_state = _shared.load_json(root / "data" / "automated" / "source_state.json", [])
    news_queue = _shared.load_json(root / "data" / "news" / "ai_news_queue.json", [])

    # 加载历史（用于计算 change_pct）。官方价格事件提供可核验的历史起点，
    # 每日快照随后覆盖同日事件并持续追加，避免用当前价格倒填未知历史。
    raw_price_events = _shared.load_json(
        root / "data" / "manual" / "token_price_events.json", {}
    ).get("records", [])
    price_events = _expand_official_price_events(raw_price_events, today)
    price_snapshots = _shared.read_jsonl(root / "data" / "history" / "token_pricing.jsonl")
    price_history_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in [*price_events, *market_price_history, *price_snapshots]:
        if row.get("date") and row.get("metric_id"):
            price_history_by_key[(row["date"], row["metric_id"])] = row
    price_history = sorted(
        price_history_by_key.values(),
        key=lambda row: (row.get("date", ""), row.get("metric_id", "")),
    )
    business_history = _shared.read_jsonl(root / "data" / "history" / "business.jsonl")
    gpu_history = _shared.read_jsonl(root / "data" / "history" / "gpu_pricing.jsonl")

    # ── 1. Token 定价模块 ──
    pricing_records = _build_pricing(
        _merge_pricing_records(manual_pricing.get("records", []), market_pricing.get("records", [])),
        models_list,
        company_by_id,
        fx,
        price_history,
        today,
    )

    # ── 2. 商业化模块 ──
    business_records = _build_business(
        manual_business.get("records", []),
        company_by_id,
        today,
    )
    business_companies = [
        {
            "id": company.get("id"),
            "name": company.get("name_zh") or company.get("name"),
            "name_en": company.get("name"),
            "region": company.get("region"),
            "type": company.get("type"),
            "listed": company.get("listed", False),
            "ticker": company.get("ticker"),
        }
        for company in companies_list
        if company.get("status") == "active"
        and company.get("type") in {"independent_model", "tech_group", "research_lab"}
    ]

    # ── 3. Compute 模块（GPU + Capex） ──
    gpu_records = _build_gpu(root, company_by_id, today)
    capex_records = _enrich_records(_merge_metric_records(
        manual_supply.get("capex_records", []), sec_fundamentals.get("capex_records", [])
    ), company_by_id, today)
    supply_chain_records = _enrich_records(_merge_metric_records(
        manual_supply.get("supply_chain_records", []), sec_fundamentals.get("supply_chain_records", [])
    ), company_by_id, today)

    # ── 4. 来源健康 ──
    source_status = _build_source_status(source_state, sources_cfg)
    health = _build_health(
        source_status, pricing_records, business_records, gpu_records,
        capex_records, supply_chain_records, market_snapshot.get("records", []), generated_at,
    )

    # ── 5. AI Cycle 评分 ──
    cycle_scores = _build_cycle_scores(
        pricing_records, business_records, gpu_records, capex_records, market_snapshot.get("records", []),
        price_history, gpu_history, source_status, cycle_cfg, companies_list, models_list, generated_at,
    )

    # ── 6. 新闻（前 20 条待复核） ──
    news_preview = []
    for item in news_queue[:20]:
        news_preview.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "publisher": item.get("publisher"),
            "published_at": item.get("published_at"),
            "status": item.get("status", "pending_review"),
            "tags": item.get("tags", []),
        })

    # ── 组装 Payload ──
    company_count = len(companies_list)
    models_with_pricing = len([r for r in pricing_records if r.get("value") is not None])
    arr_disclosed = len([r for r in business_records
                        if r.get("value") is not None and r.get("metric_category") == "business"])

    payload: dict[str, Any] = {
        "meta": {
            "title": "AI Industry Monitor",
            "subtitle": "AI产业与大模型商业化监测 Dashboard",
            "generated_at": generated_at,
            "schedule": "每日 09:00 (Asia/Shanghai)",
            "data_policy": "公开可引用数据。sample/missing/manual_required 标记明确。",
            "fx": {"cny_per_usd": fx, "note": "仅用于跨币种横向比较"},
        },
        "kpis": {
            "companies": company_count,
            "models_with_pricing": models_with_pricing,
            "source_ok": health["sources_ok"],
            "source_total": health["sources_total"],
            "business_disclosures": arr_disclosed,
            "arr_disclosures": arr_disclosed,
        },
        "overview": {
            "cycle": cycle_scores,
            "kpi_summary": _kpi_summary(pricing_records, business_records),
        },
        "token_pricing": {
            "records": pricing_records,
            "latest_models": market_pricing.get("discovery_records", []),
            "methodology": {
                "blended_formula": "input × 0.65 + output × 0.35 (USD)",
                "comparability": "不同币种按fx_rate转USD；Batch/缓存/长上下文/企业折扣不包含在内。",
            },
        },
        "business": {
            "records": business_records,
            "companies": business_companies,
            "methodology": {
                "note": "ARR/年化运行率、财务收入、用户、企业采用、融资和估值按统一列展示；不同口径不强行合并，未披露≠0。",
            },
        },
        "compute": {
            "gpu": gpu_records,
            "capex": capex_records,
            "note": "GPU价格来自公开按需定价页。整机/合约/竞价价格不混排。",
        },
        "supply_chain": {
            "records": supply_chain_records,
            "note": "公司年报、业绩公告与监管披露均为公司整体口径，不等同于AI业务收入；保留原币种与财年边界，用于观察产业链经营趋势。"
        },
        "investment": {
            "watchlist": _shared.load_json(root / "config" / "watchlist.json", {}),
            "market": market_snapshot,
            "note": "行情与估值接口为可选增强；未配置API时不输出伪数据。"
        },
        "history": {
            # 约可保留 30 个模型每日快照 22 个月，避免长期曲线被全局截断。
            "token_pricing": price_history[-20000:],
            "business": business_history[-500:],
            "gpu_pricing": gpu_history[-500:],
            "cycle_scores": _shared.read_jsonl(root / "data" / "history" / "cycle_scores.jsonl")[-200:],
            "capex": _shared.read_jsonl(root / "data" / "history" / "capex.jsonl")[-300:],
            "runs": _shared.read_jsonl(root / "data" / "history" / "runs.jsonl")[-100:],
        },
        "sources": source_status,
        "news": news_preview,
        "health": health,
        "methodology": {
            "data_boundary": "T1=官方一手, T2=权威媒体/公开研究, T3=聚合/自媒体",
            "news_policy": "RSS新闻仅进入待复核池，不自动写入正式指标",
            "missing_policy": "缺失数据value=null，不写作0",
            "sample_policy": "示例数据标记confidence=sample，不应被引用",
            "cycle_note": cycle_cfg.get("_scoring_philosophy", ""),
        },
    }

    # ── 写入文件 ──
    _shared.atomic_write(root / "data" / "automated" / "dashboard.json", payload)
    _shared.atomic_write(root / "data" / "automated" / "health.json", health)
    _shared.atomic_write(root / "data" / "automated" / "cycle_scores.json", cycle_scores)

    # ── 追加历史 ──
    snapshot_date = generated_at[:10]
    for rec in pricing_records:
        _shared.append_jsonl(
            root / "data" / "history" / "token_pricing.jsonl",
            {"date": snapshot_date, "metric_id": rec["metric_id"],
             "value": rec.get("value"), "currency": rec.get("currency"),
             "blended_cost_usd": rec.get("blended_cost_usd"),
             "provider_model_id": rec.get("provider_model_id"),
             "source_name": rec.get("source_name"), "source_url": rec.get("source_url"),
             "source_tier": rec.get("source_tier"),
             "evidence_status": rec.get("evidence_status")},
            dedupe_keys=["date", "metric_id"],
        )
    for rec in business_records:
        _shared.append_jsonl(
            root / "data" / "history" / "business.jsonl",
            {"date": snapshot_date, "metric_id": rec["metric_id"],
             "value": rec.get("value"), "unit": rec.get("unit")},
            dedupe_keys=["date", "metric_id"],
        )
    for rec in gpu_records:
        _shared.append_jsonl(
            root / "data" / "history" / "gpu_pricing.jsonl",
            {"date": snapshot_date, "metric_id": rec.get("metric_id"),
             "value": rec.get("value")},
            dedupe_keys=["date", "metric_id"],
        )
    for rec in capex_records:
        _shared.append_jsonl(
            root / "data" / "history" / "capex.jsonl",
            {"date": snapshot_date, "metric_id": rec.get("metric_id"), "value": rec.get("value"),
             "company_id": rec.get("company_id"), "period": rec.get("period")},
            dedupe_keys=["date", "metric_id"],
        )
    _shared.append_jsonl(
        root / "data" / "history" / "cycle_scores.jsonl",
        {"date": snapshot_date, **cycle_scores},
        dedupe_keys=["date"],
    )

    if verbose:
        print(f"[build_dashboard] dashboard.json 已生成 ({len(pricing_records)} pricing + "
              f"{len(business_records)} business + {len(gpu_records)} gpu)")

    return payload


def _merge_pricing_records(manual: list[dict[str, Any]], automated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer verified manual vendor prices; use T3 market routes only for gaps."""
    auto_by_model = {r.get("model_id"): r for r in automated if r.get("model_id")}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in manual:
        model_id = record.get("model_id")
        if record.get("value") is not None or model_id not in auto_by_model:
            merged.append(dict(record))
        else:
            replacement = dict(auto_by_model[model_id])
            replacement["official_source_url"] = record.get("source_url")
            merged.append(replacement)
        seen.add(model_id)
    merged.extend(dict(r) for r in automated if r.get("model_id") not in seen)
    return merged


def _merge_metric_records(manual: list[dict[str, Any]], automated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge by metric_id, preferring a non-null automated regulatory fact."""
    combined = {r.get("metric_id"): dict(r) for r in manual if r.get("metric_id") and r.get("value") is not None}
    for record in automated:
        if record.get("metric_id") and record.get("value") is not None:
            combined[record["metric_id"]] = dict(record)
    return list(combined.values())


def _enrich_records(records: list[dict[str, Any]], company_by_id: dict[str, dict[str, Any]], today: Any) -> list[dict[str, Any]]:
    out = []
    for original in records:
        rec = dict(original)
        company = company_by_id.get(rec.get("company_id"), {})
        rec["company_name"] = company.get("name_zh", company.get("name", rec.get("company_id")))
        rec["freshness"] = _shared.freshness(rec.get("as_of_date"), today=today)
        out.append(rec)
    return sorted(out, key=lambda x: (x.get("company_id", ""), x.get("as_of_date", "")), reverse=True)


# ── Token 定价 ────────────────────────────────────────────────────

def _build_pricing(
    records: list[dict[str, Any]],
    models: list[dict[str, Any]],
    company_by_id: dict[str, dict[str, Any]],
    fx: float,
    history: list[dict[str, Any]],
    today: Any,
) -> list[dict[str, Any]]:
    """处理 Token 定价记录——计算混合成本和环比变化。"""
    model_map = {m["id"]: m for m in models}
    # 历史按 metric_id 组织
    hist_by_id: dict[str, float] = {}
    for h in history:
        hid = h.get("metric_id", "")
        val = h.get("blended_cost_usd") or h.get("value")
        if hid and val is not None:
            hist_by_id[hid] = float(val)

    out: list[dict[str, Any]] = []
    for rec in records:
        mid = rec.get("model_id", "")
        cid = rec.get("company_id", "")
        company = company_by_id.get(cid, {})
        model = model_map.get(mid, {})

        rec["company_name"] = company.get("name_zh", company.get("name", cid))
        rec["region"] = company.get("region", "overseas")
        rec["model_status"] = model.get("status", "unknown")

        # ── 计算混合成本 (blended_cost_usd) ──
        metric_id = rec.get("metric_id", "")
        cat = rec.get("metric_category", "")
        currency = rec.get("currency", "USD")
        val = rec.get("value")

        # 情况1: metric_id 中包含 "blended_cost" 且 value 不为 None
        if cat == "token_pricing" and "blended_cost" in metric_id and val is not None:
            blended = float(val)
            if currency.upper() == "CNY":
                blended = round(blended / fx, 6)
            rec["blended_cost_usd"] = blended

        # 情况2: 有 input/output 明细 → 用 _shared.blended_cost 计算
        elif cat == "token_pricing" and "input_per_m" in rec:
            inp_p = rec.get("input_per_m")
            out_p = rec.get("output_per_m")
            if inp_p is not None and out_p is not None:
                rec["blended_cost_usd"] = _shared.blended_cost(
                    float(inp_p), float(out_p),
                    input_weight=0.65, output_weight=0.35,
                )
                # 如果是 CNY，转换为 USD
                if currency.upper() == "CNY" and rec["blended_cost_usd"] is not None:
                    rec["blended_cost_usd"] = _shared.normalize_currency(
                        rec["blended_cost_usd"], "CNY", fx={"cny_per_usd": fx}
                    )
            else:
                rec["blended_cost_usd"] = None

        # 情况3: 数据缺失
        else:
            rec["blended_cost_usd"] = None

        # 环比变化
        prev = hist_by_id.get(rec.get("metric_id"))
        cur = rec.get("blended_cost_usd") or rec.get("value")
        if prev is not None and cur is not None:
            rec["change_pct"] = round((float(cur) / prev - 1) * 100, 2)
        else:
            rec["change_pct"] = None

        # 新鲜度
        rec["freshness"] = _shared.freshness(rec.get("as_of_date"), today=today)
        out.append(rec)

    # 按混合成本升序
    out.sort(key=lambda r: r.get("blended_cost_usd") or 999)
    return out


# ── 商业化 ─────────────────────────────────────────────────────────

def _build_business(
    records: list[dict[str, Any]],
    company_by_id: dict[str, dict[str, Any]],
    today: Any,
) -> list[dict[str, Any]]:
    """处理商业化指标记录。"""
    out: list[dict[str, Any]] = []
    for rec in records:
        cid = rec.get("company_id", "")
        company = company_by_id.get(cid, {})
        rec["company_name"] = company.get("name_zh", company.get("name", cid))
        rec["region"] = company.get("region", "overseas")
        rec["freshness"] = _shared.freshness(rec.get("as_of_date"), today=today)
        out.append(rec)
    out.sort(key=lambda r: float(r.get("value") or 0), reverse=True)
    return out


# ── GPU ────────────────────────────────────────────────────────────

def _build_gpu(
    root: Path, company_by_id: dict[str, dict[str, Any]], today: Any
) -> list[dict[str, Any]]:
    """构造 GPU 指标记录，优先使用已解析的标准化价格。"""
    parsed = _shared.load_json(root / "data" / "automated" / "gpu_pricing.json", {}).get("records", [])
    if parsed:
        return _enrich_records(parsed, company_by_id, today)
    source_state = _shared.load_json(root / "data" / "automated" / "source_state.json", [])
    gpu_related = [s for s in source_state if s.get("kind") in ("gpu_rental", "gpu_rental_cloud")]

    records: list[dict[str, Any]] = []
    for gs in gpu_related:
        records.append({
            "metric_id": f"gpu_source_state::{gs.get('source_id','')}",
            "metric_name": gs.get("name", ""),
            "metric_category": "gpu_pricing",
            "value": None,
            "unit": "source_state",
            "currency": None,
            "company_id": None,
            "model_id": None,
            "region": "global",
            "period": _shared.today_shanghai(),
            "as_of_date": _shared.today_shanghai(),
            "collected_at": gs.get("checked_at", ""),
            "source_name": gs.get("name", ""),
            "source_url": gs.get("url", ""),
            "source_tier": 1,
            "evidence_status": "public_snapshot" if gs.get("status") == "ok" else "manual_required",
            "confidence": "inferred" if gs.get("status") == "ok" else "missing",
            "note": f"GPU源状态: {gs.get('status','')}. 价格解析待后续版本实现。",
            "freshness": _shared.freshness(
                (gs.get("checked_at") or "")[:10], today=today
            ),
        })
    return records


# ── 来源健康 ──────────────────────────────────────────────────────

def _build_source_status(
    state: list[dict[str, Any]], sources_cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """整理来源状态。"""
    out: list[dict[str, Any]] = []
    for s in state:
        out.append({
            "source_id": s.get("source_id"),
            "name": s.get("name"),
            "url": s.get("url"),
            "kind": s.get("kind"),
            "status": s.get("status"),
            "checked_at": s.get("checked_at"),
            "changed": s.get("changed"),
            "text_chars": s.get("text_chars"),
            "error": s.get("error"),
        })
    return out


def _build_health(
    sources: list[dict[str, Any]],
    pricing: list[dict[str, Any]],
    business: list[dict[str, Any]],
    gpu: list[dict[str, Any]],
    capex: list[dict[str, Any]],
    supply_chain: list[dict[str, Any]],
    market: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """生成系统健康报告。"""
    ok = sum(1 for s in sources if s.get("status") == "ok")
    total = len(sources)
    missing_pricing = sum(1 for p in pricing if p.get("value") is None)
    missing_business = sum(1 for b in business if b.get("value") is None)
    sample_count = sum(1 for p in pricing if p.get("confidence") == "sample")
    failed = total - ok

    if total == 0 or ok == 0:
        status = "partial"
    elif ok < total:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "generated_at": generated_at,
        "sources_ok": ok,
        "sources_total": total,
        "sources_failed": failed,
        "source_success_rate": f"{ok}/{total}" if total else "0/0",
        "pricing_total": len(pricing),
        "pricing_missing": missing_pricing,
        "pricing_sample": sample_count,
        "business_total": len(business),
        "business_missing": missing_business,
        "gpu_records": sum(1 for r in gpu if r.get("value") is not None),
        "capex_records": sum(1 for r in capex if r.get("value") is not None),
        "supply_chain_records": sum(1 for r in supply_chain if r.get("value") is not None),
        "market_records": sum(1 for r in market if r.get("close") is not None),
        "warnings": (
            [f"{missing_pricing} pricing records have null values"]
            if missing_pricing else []
        ) + (
            [f"{sample_count} pricing records are SAMPLES — do not cite as real data"]
            if sample_count else []
        ) + (
            [f"{missing_business} business records have null values"]
            if missing_business else []
        ) + (
            [f"{failed} sources are unavailable or using stale fallback"]
            if failed else []
        ),
    }


# ── AI Cycle ──────────────────────────────────────────────────────

def _build_cycle_scores(
    pricing: list[dict[str, Any]],
    business: list[dict[str, Any]],
    gpu: list[dict[str, Any]],
    capex: list[dict[str, Any]],
    market: list[dict[str, Any]],
    price_history: list[dict[str, Any]],
    gpu_history: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    cycle_cfg: dict[str, Any],
    companies: list[dict[str, Any]],
    models: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Build a transparent, reproducible proxy index for the AI cycle.

    This is deliberately a monitoring index rather than a fitted forecasting
    model. Every component exposes its raw observation, normalisation rule,
    sample size, weight, contribution and source references.
    """
    factors = cycle_cfg.get("industry_factors", {})
    stages = cycle_cfg.get("stages", [])
    pricing_with_value = [p for p in pricing if p.get("value") is not None]
    business_with_value = [b for b in business if b.get("value") is not None]
    sources_ok = sum(1 for s in sources if s.get("status") == "ok")
    real_pricing = [p for p in pricing_with_value if p.get("confidence") != "sample"]
    real_business = [b for b in business_with_value if b.get("confidence") != "sample"]
    real_gpu = [g for g in gpu if g.get("value") is not None]
    real_capex = [c for c in capex if c.get("value") is not None]

    def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    def source_refs(rows: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
        seen: set[str] = set()
        refs: list[dict[str, Any]] = []
        for row in rows:
            url = row.get("source_url") or row.get("pricing_source_url")
            if not url or url in seen:
                continue
            seen.add(url)
            refs.append({
                "name": row.get("source_name") or row.get("name") or "公开来源",
                "url": url,
                "tier": row.get("source_tier", 1 if row.get("pricing_source_url") else None),
            })
            if len(refs) >= limit:
                break
        return refs

    def component(
        component_id: str,
        label: str,
        score: float | None,
        weight: float,
        raw_display: str,
        formula: str,
        sample_size: int,
        rows: list[dict[str, Any]],
        note: str = "",
    ) -> dict[str, Any]:
        return {
            "id": component_id,
            "label": label,
            "score": round(score, 1) if score is not None else None,
            "configured_weight": weight,
            "raw_display": raw_display,
            "formula": formula,
            "sample_size": sample_size,
            "sources": source_refs(rows),
            "note": note,
        }

    def aggregate_components(items: list[dict[str, Any]]) -> tuple[float | None, float]:
        present = [item for item in items if item.get("score") is not None]
        available_weight = sum(float(item["configured_weight"]) for item in present)
        for item in items:
            if item.get("score") is None or available_weight <= 0:
                item["effective_weight"] = 0.0
                item["contribution"] = None
            else:
                effective = float(item["configured_weight"]) / available_weight
                item["effective_weight"] = round(effective, 4)
                item["contribution"] = round(float(item["score"]) * effective, 1)
        if available_weight <= 0:
            return None, 0.0
        score = sum(float(item["score"]) * float(item["configured_weight"]) for item in present) / available_weight
        return round(score, 1), round(available_weight, 2)

    # ── Technology maturity ──────────────────────────────────
    production_models = [m for m in models if m.get("status") == "production"]
    production_ids = {m.get("id") for m in production_models}
    priced_ids = {p.get("model_id") for p in real_pricing if p.get("model_id") in production_ids}
    pricing_coverage = (len(priced_ids) / len(production_ids) * 100) if production_ids else None

    multimodal_score = (
        sum(1 for m in production_models if len(m.get("modalities") or []) >= 2) / len(production_models) * 100
        if production_models else None
    )
    context_known = [m for m in production_models if isinstance(m.get("context_window_k"), (int, float))]
    frontier_context_score = (
        sum(1 for m in context_known if float(m["context_window_k"]) >= 1000) / len(context_known) * 100
        if context_known else None
    )

    # Prefer one (highest-source-quality) series per model to avoid counting
    # official and routed versions of the same model twice.
    chosen_pricing: dict[str, dict[str, Any]] = {}
    for row in sorted(real_pricing, key=lambda r: (r.get("source_tier", 9), r.get("tier") != "standard")):
        chosen_pricing.setdefault(str(row.get("model_id")), row)
    history_by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in price_history:
        raw_value = row.get("blended_cost_usd", row.get("value"))
        if row.get("metric_id") and row.get("date") and isinstance(raw_value, (int, float)):
            history_by_metric.setdefault(row["metric_id"], []).append(row | {"_score_value": float(raw_value)})
    price_changes: list[float] = []
    price_change_rows: list[dict[str, Any]] = []
    for current in chosen_pricing.values():
        rows = sorted(history_by_metric.get(current.get("metric_id"), []), key=lambda r: r["date"])
        by_date = {row["date"]: row for row in rows}
        rows = [by_date[key] for key in sorted(by_date)]
        if len(rows) < 2:
            continue
        span_days = (date.fromisoformat(rows[-1]["date"]) - date.fromisoformat(rows[0]["date"])).days
        if span_days < 30 or rows[0]["_score_value"] <= 0:
            continue
        latest_date = date.fromisoformat(rows[-1]["date"])
        cutoff = latest_date - timedelta(days=90)
        start = next((row for row in rows if date.fromisoformat(row["date"]) >= cutoff), rows[0])
        change = (rows[-1]["_score_value"] / start["_score_value"] - 1) * 100
        price_changes.append(change)
        price_change_rows.extend([start, rows[-1]])
    median_price_change = statistics.median(price_changes) if price_changes else None
    price_decline_score = clamp(50 - 2 * median_price_change) if median_price_change is not None else None

    tech_components = [
        component(
            "token_price_decline", "90天Token成本变化", price_decline_score, 0.35,
            f"中位数 {median_price_change:+.1f}%" if median_price_change is not None else "不足30天的可比序列",
            "score = clip(50 − 2 × 90天价格变化中位数, 0, 100)；下降25%=100，持平=50，上涨25%=0",
            len(price_changes), price_change_rows,
            "同一模型只选来源等级最高的一条序列，避免官方价与路由价重复计数。",
        ),
        component(
            "public_price_coverage", "生产模型价格覆盖", pricing_coverage, 0.25,
            f"{len(priced_ids)} / {len(production_ids)} 个生产模型" if production_ids else "无生产模型",
            "score = 有真实价格的生产模型数 ÷ 已登记生产模型数 × 100",
            len(production_ids), list(chosen_pricing.values()),
            "衡量可获得性与透明度，是技术成熟度的代理，不等同于模型能力。",
        ),
        component(
            "frontier_context_coverage", "百万Token上下文覆盖", frontier_context_score, 0.20,
            f"{sum(1 for m in context_known if float(m['context_window_k']) >= 1000)} / {len(context_known)} 个已知模型" if context_known else "无可比数据",
            "score = 上下文窗口≥1000K的生产模型数 ÷ 上下文已披露模型数 × 100",
            len(context_known), context_known,
        ),
        component(
            "multimodal_coverage", "多模态覆盖", multimodal_score, 0.20,
            f"{sum(1 for m in production_models if len(m.get('modalities') or []) >= 2)} / {len(production_models)} 个生产模型" if production_models else "无可比数据",
            "score = 支持至少两种模态的生产模型数 ÷ 生产模型数 × 100",
            len(production_models), production_models,
        ),
    ]
    tech_score, tech_available_weight = aggregate_components(tech_components)

    # ── Commercialisation ────────────────────────────────────
    arr_rows = [r for r in real_business if str(r.get("metric_id", "")).startswith("arr::") and float(r.get("value") or 0) > 0]
    user_rows = [r for r in real_business if str(r.get("metric_id", "")).startswith("user_count::") and float(r.get("value") or 0) > 0]
    enterprise_rows = [r for r in real_business if str(r.get("metric_id", "")).startswith("enterprise_customers::") and float(r.get("value") or 0) > 0]
    business_company_ids = {
        c.get("id") for c in companies
        if c.get("status") == "active"
        and c.get("type") in {"independent_model", "tech_group", "research_lab"}
    }
    commercial_rows = arr_rows + user_rows + enterprise_rows
    total_arr = sum(float(r["value"]) for r in arr_rows)
    max_users = max((float(r["value"]) for r in user_rows), default=0.0)
    total_enterprise = sum(float(r["value"]) for r in enterprise_rows)
    disclosed_companies = {r.get("company_id") for r in commercial_rows if r.get("company_id")}
    arr_score = clamp(total_arr / 200 * 100) if arr_rows else None
    user_score = clamp(max_users / 1_000_000_000 * 100) if user_rows else None
    enterprise_score = clamp(total_enterprise / 1_000_000 * 100) if enterprise_rows else None
    disclosure_score = len(disclosed_companies) / len(business_company_ids) * 100 if business_company_ids else None
    biz_components = [
        component(
            "arr_scale", "ARR/年化收入规模", arr_score, 0.40,
            f"合计 ${total_arr:.1f}B；{len(arr_rows)} 条披露" if arr_rows else "暂无有效披露",
            "score = clip(已披露ARR合计 ÷ $200B × 100, 0, 100)", len(arr_rows), arr_rows,
            "不同公司口径可能为ARR或年化运行率；仅作规模代理，不视为审计收入。",
        ),
        component(
            "user_adoption", "终端用户采用", user_score, 0.25,
            f"最高 {max_users/1_000_000:.0f}M 活跃用户" if user_rows else "暂无有效披露",
            "score = clip(最高已披露活跃用户数 ÷ 10亿 × 100, 0, 100)", len(user_rows), user_rows,
            "不同公司用户口径不直接相加，取单项最高披露避免重复用户。",
        ),
        component(
            "enterprise_adoption", "企业客户采用", enterprise_score, 0.20,
            f"合计 {total_enterprise:,.0f} 家" if enterprise_rows else "缺失，不以0代替",
            "score = clip(企业客户合计 ÷ 100万 × 100, 0, 100)", len(enterprise_rows), enterprise_rows,
        ),
        component(
            "commercial_disclosure_breadth", "商业披露覆盖", disclosure_score, 0.15,
            f"{len(disclosed_companies)} / {len(business_company_ids)} 家模型与AI公司" if business_company_ids else "无公司样本",
            "score = 有ARR/用户/企业客户披露的公司数 ÷ 监测公司数 × 100",
            len(business_company_ids), commercial_rows,
        ),
    ]
    biz_score, biz_available_weight = aggregate_components(biz_components)

    # ── Capital investment ───────────────────────────────────
    by_company: dict[str, list[dict[str, Any]]] = {}
    for rec in real_capex:
        by_company.setdefault(rec.get("company_id", ""), []).append(rec)
    growth_rates: list[float] = []
    growth_rows: list[dict[str, Any]] = []
    for rows in by_company.values():
        unique_periods = {str(row.get("period")): row for row in rows}
        ordered = sorted(unique_periods.values(), key=lambda r: r.get("as_of_date", ""))
        if len(ordered) >= 2 and float(ordered[-2].get("value") or 0) > 0:
            growth_rates.append((float(ordered[-1]["value"]) / float(ordered[-2]["value"]) - 1) * 100)
            growth_rows.extend(ordered[-2:])
    median_capex_growth = statistics.median(growth_rates) if growth_rates else None
    capex_growth_score = clamp(50 + 1.25 * median_capex_growth) if median_capex_growth is not None else None
    csp_ids = {"microsoft", "google", "amazon", "meta"}
    capex_covered = {r.get("company_id") for r in real_capex if r.get("company_id") in csp_ids}
    capex_coverage_score = len(capex_covered) / len(csp_ids) * 100
    generated_day = date.fromisoformat(generated_at[:10])
    recent_funding = [
        r for r in real_business
        if str(r.get("metric_id", "")).startswith("funding::")
        and r.get("unit") == "USD_billion"
        and r.get("as_of_date")
        and (generated_day - date.fromisoformat(r["as_of_date"])).days <= 365
    ]
    funding_total = sum(float(r["value"]) for r in recent_funding)
    funding_score = clamp(funding_total / 100 * 100) if recent_funding else None

    gpu_by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in gpu_history:
        if row.get("metric_id") and isinstance(row.get("value"), (int, float)):
            gpu_by_metric.setdefault(row["metric_id"], []).append(row)
    gpu_changes: list[float] = []
    for rows in gpu_by_metric.values():
        by_day = {row.get("date"): row for row in rows if row.get("date")}
        ordered = [by_day[key] for key in sorted(by_day)]
        if len(ordered) >= 2:
            span = (date.fromisoformat(ordered[-1]["date"]) - date.fromisoformat(ordered[0]["date"])).days
            if span >= 30 and float(ordered[0]["value"]) > 0:
                gpu_changes.append((float(ordered[-1]["value"]) / float(ordered[0]["value"]) - 1) * 100)
    median_gpu_change = statistics.median(gpu_changes) if gpu_changes else None
    gpu_tightness_score = clamp(50 + 2 * median_gpu_change) if median_gpu_change is not None else None
    capital_components = [
        component(
            "csp_capex_growth", "CSP资本开支增速", capex_growth_score, 0.50,
            f"同比中位数 {median_capex_growth:+.1f}%" if median_capex_growth is not None else "缺少至少两期可比数据",
            "score = clip(50 + 1.25 × CSP公司CAPEX同比中位数, 0, 100)；0%=50，+40%=100，−40%=0",
            len(growth_rates), growth_rows,
            "采用公司整体CAPEX，可能包含非AI投入。",
        ),
        component(
            "csp_capex_coverage", "四大CSP披露覆盖", capex_coverage_score, 0.20,
            f"{len(capex_covered)} / {len(csp_ids)} 家", "score = 有有效CAPEX披露的四大CSP数 ÷ 4 × 100",
            len(csp_ids), real_capex,
        ),
        component(
            "recent_funding", "近12个月模型公司融资", funding_score, 0.15,
            f"合计 ${funding_total:.1f}B" if recent_funding else "暂无有效披露",
            "score = clip(近12个月已披露融资额 ÷ $100B × 100, 0, 100)", len(recent_funding), recent_funding,
        ),
        component(
            "gpu_price_tightness", "GPU租赁价格趋势", gpu_tightness_score, 0.15,
            f"变化中位数 {median_gpu_change:+.1f}%" if median_gpu_change is not None else "不足30天，不计分",
            "score = clip(50 + 2 × 至少30天GPU价格变化中位数, 0, 100)", len(gpu_changes), real_gpu,
            "高分表示租赁价格上涨/供需偏紧，不代表投资回报更高。",
        ),
    ]
    capital_score, capital_available_weight = aggregate_components(capital_components)

    factor_scores = {
        "technology_maturity": {
            "score": tech_score, "weight": float(factors.get("technology_maturity", {}).get("weight", 0.30)),
            "available": tech_score is not None, "available_component_weight": tech_available_weight,
            "components": tech_components,
        },
        "commercialization": {
            "score": biz_score, "weight": float(factors.get("commercialization", {}).get("weight", 0.35)),
            "available": biz_score is not None, "available_component_weight": biz_available_weight,
            "components": biz_components,
        },
        "capital_investment": {
            "score": capital_score, "weight": float(factors.get("capital_investment", {}).get("weight", 0.35)),
            "available": capital_score is not None, "available_component_weight": capital_available_weight,
            "components": capital_components,
        },
    }
    available_factors = [factor for factor in factor_scores.values() if factor["available"]]
    sufficient_industry_data = len(available_factors) >= 2
    if sufficient_industry_data:
        factor_weight_sum = sum(float(factor["weight"]) for factor in available_factors)
        industry_score = round(sum(float(factor["score"]) * float(factor["weight"]) for factor in available_factors) / factor_weight_sum, 1)
        for factor in factor_scores.values():
            effective = float(factor["weight"]) / factor_weight_sum if factor["available"] else 0.0
            factor["effective_weight"] = round(effective, 4)
            factor["contribution"] = round(float(factor["score"]) * effective, 1) if factor["available"] else None
    else:
        industry_score = None
        for factor in factor_scores.values():
            factor["effective_weight"] = 0.0
            factor["contribution"] = None

    # ── Market-price crowding proxy ───────────────────────────
    market_3m = [float(r["return_3m_pct"]) for r in market if r.get("return_3m_pct") is not None]
    market_dd = [float(r["drawdown_52w_pct"]) for r in market if r.get("drawdown_52w_pct") is not None]
    median_momentum = statistics.median(market_3m) if market_3m else None
    breadth = sum(1 for value in market_3m if value > 0) / len(market_3m) * 100 if market_3m else None
    median_drawdown = statistics.median(market_dd) if market_dd else None
    risk_details = [
        component(
            "momentum", "3个月价格动量", clamp(50 + 1.25 * median_momentum) if median_momentum is not None else None,
            0.40, f"中位收益 {median_momentum:+.1f}%" if median_momentum is not None else "缺失",
            "score = clip(50 + 1.25 × 观察池3个月收益率中位数, 0, 100)", len(market_3m), market,
        ),
        component(
            "breadth", "上涨广度", breadth, 0.30,
            f"{sum(1 for value in market_3m if value > 0)} / {len(market_3m)} 个标的上涨" if market_3m else "缺失",
            "score = 3个月收益为正的标的数 ÷ 有效标的数 × 100", len(market_3m), market,
        ),
        component(
            "proximity_to_52w_high", "距52周高点", clamp(100 + median_drawdown) if median_drawdown is not None else None,
            0.30, f"距高点中位数 {median_drawdown:.1f}%" if median_drawdown is not None else "缺失",
            "score = clip(100 + 距52周高点回撤中位数, 0, 100)", len(market_dd), market,
        ),
    ]
    risk_score, risk_available_weight = aggregate_components(risk_details)
    risk_components = {item["id"]: item["score"] for item in risk_details if item.get("score") is not None}

    # ── Deterioration triggers and stage decision ─────────────
    capex_deceleration_available = False
    capex_deceleration = False
    for rows in by_company.values():
        unique_periods = {str(row.get("period")): row for row in rows}
        ordered = sorted(unique_periods.values(), key=lambda r: r.get("as_of_date", ""))
        if len(ordered) >= 3 and all(float(row.get("value") or 0) > 0 for row in ordered[-3:]):
            capex_deceleration_available = True
            previous_growth = float(ordered[-2]["value"]) / float(ordered[-3]["value"]) - 1
            latest_growth = float(ordered[-1]["value"]) / float(ordered[-2]["value"]) - 1
            capex_deceleration = capex_deceleration or latest_growth < previous_growth
    gpu_decline_available = any(len({row.get("date") for row in rows}) >= 3 for rows in gpu_by_metric.values())
    gpu_decline = False
    if gpu_decline_available:
        gpu_decline = any(
            len(ordered := sorted({row.get("date"): float(row["value"]) for row in rows if row.get("date")}.items())) >= 3
            and ordered[-3][1] > ordered[-2][1] > ordered[-1][1]
            for rows in gpu_by_metric.values()
        )
    median_market_return = statistics.median(market_3m) if market_3m else None
    triggers = [
        {"id": "capex_deceleration", "label": "CAPEX增速连续放缓", "available": capex_deceleration_available, "triggered": capex_deceleration if capex_deceleration_available else None, "rule": "同一公司至少3期CAPEX，最近一期同比低于前一期同比"},
        {"id": "gpu_price_decline", "label": "GPU价格连续两期回落", "available": gpu_decline_available, "triggered": gpu_decline if gpu_decline_available else None, "rule": "同一GPU价格序列最近3个有效观察值连续下降"},
        {"id": "arr_expectation_miss", "label": "ARR低于一致预期", "available": False, "triggered": None, "rule": "需要可授权的一致预期数据，当前未接入"},
        {"id": "extreme_crowding", "label": "市场拥挤代理≥85", "available": risk_score is not None, "triggered": risk_score >= 85 if risk_score is not None else None, "rule": "risk_crowding_score ≥ 85"},
        {"id": "market_correction", "label": "观察池显著回撤", "available": median_market_return is not None, "triggered": median_market_return <= -20 if median_market_return is not None else None, "rule": "观察池3个月收益率中位数 ≤ −20%"},
    ]
    deterioration_count = sum(1 for item in triggers if item.get("triggered") is True)
    if sufficient_industry_data and industry_score is not None:
        stage_id, stage_label = _determine_stage(industry_score, risk_score or 50.0, stages, deterioration_count)
    else:
        stage_id, stage_label = ("insufficient_data", "数据不足")

    stage_checks = [
        {"stage_id": "insufficient_data", "label": "数据不足", "rule": "三项产业因子中少于2项可计算", "matched": not sufficient_industry_data},
        {"stage_id": "cyclical_adjustment", "label": "周期调整期", "rule": "5项恶化信号中至少2项触发", "matched": deterioration_count >= 2},
        {"stage_id": "valuation_crowding", "label": "市场拥挤警戒", "rule": "产业发展强度≥55 且市场拥挤代理≥70", "matched": industry_score is not None and industry_score >= 55 and risk_score is not None and risk_score >= 70},
        {"stage_id": "commercialization", "label": "商业化兑现期", "rule": "产业发展强度≥55 且市场拥挤代理<70", "matched": industry_score is not None and industry_score >= 55 and (risk_score is None or risk_score < 70)},
        {"stage_id": "infra_expansion", "label": "基础设施扩张期", "rule": "35≤产业发展强度<55", "matched": industry_score is not None and 35 <= industry_score < 55},
        {"stage_id": "tech_validation", "label": "技术验证期", "rule": "产业发展强度<35", "matched": industry_score is not None and industry_score < 35},
    ]

    missing_components = sum(
        1 for factor in factor_scores.values() for item in factor["components"] if item.get("score") is None
    )
    capex_growth_companies = len(growth_rates)
    confidence_reasons: list[str] = []
    if len(disclosed_companies) < 5:
        confidence_reasons.append(f"商业采用类有效披露覆盖 {len(disclosed_companies)} 家公司，仍需继续扩展")
    if capex_growth_companies < 2:
        confidence_reasons.append(f"仅 {capex_growth_companies} 家CSP具备两期可比CAPEX")
    if not enterprise_rows:
        confidence_reasons.append("企业客户数缺失")
    if not gpu_changes:
        confidence_reasons.append("GPU价格历史不足30天")
    if market and all(int(row.get("source_tier") or 9) >= 3 for row in market):
        confidence_reasons.append("市场拥挤度仅使用T3免费行情代理")
    total_sources = len(sources)
    all_components = [
        item for factor in factor_scores.values() for item in factor["components"]
    ] + risk_details
    available_components = sum(1 for item in all_components if item.get("score") is not None)
    component_coverage = available_components / len(all_components) if all_components else 0.0
    evidence_rows = real_pricing + real_business + real_gpu + real_capex
    strong_evidence_rows = [
        row for row in evidence_rows
        if int(row.get("source_tier") or 9) <= 2
        and row.get("confidence") in {"verified", "reported", "inferred"}
    ]
    evidence_quality = len(strong_evidence_rows) / len(evidence_rows) if evidence_rows else 0.0
    source_reliability = sources_ok / total_sources if total_sources else 0.0
    confidence_score = round(
        (component_coverage * 0.45 + evidence_quality * 0.40 + source_reliability * 0.15) * 100,
        1,
    )
    if not sufficient_industry_data:
        confidence = "missing"
    elif confidence_score >= 85:
        confidence = "high"
    elif confidence_score >= 65:
        confidence = "medium"
    else:
        confidence = "limited"

    return {
        "generated_at": generated_at,
        "stage_id": stage_id,
        "stage_label": stage_label,
        "stage_description": next((item.get("description") for item in stages if item.get("id") == stage_id), ""),
        "industry_development_score": industry_score,
        "risk_crowding_score": risk_score,
        "risk_note": "仅为市场价格拥挤代理：使用3个月动量、上涨广度与距52周高点；未接入Forward P/E、EV/EBITDA或ETF净申购，因此不能称为完整估值拥挤度，也不能单独作为交易信号。" if risk_score is not None else "行情覆盖不足，市场拥挤代理暂不输出。",
        "risk_components": risk_components,
        "risk_details": {"score": risk_score, "available_component_weight": risk_available_weight, "components": risk_details},
        "factor_scores": factor_scores,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "confidence_dimensions": {
            "component_coverage_pct": round(component_coverage * 100, 1),
            "strong_evidence_pct": round(evidence_quality * 100, 1),
            "source_reliability_pct": round(source_reliability * 100, 1),
            "formula": "证据覆盖分 = 可计算子因子覆盖×45% + T1/T2强证据占比×40% + 自动数据源成功率×15%",
        },
        "confidence_reasons": confidence_reasons,
        "score_method": "transparent_proxy_v2",
        "methodology": {
            "positioning": "可复现的产业监测代理指数，不是经回测验证的收益预测模型，也不是投资评级。",
            "industry_formula": "产业发展强度 = 技术成熟度×30% + 商业化兑现度×35% + 资本投入强度×35%；缺失整项时对可用权重归一化。",
            "industry_calculation": " + ".join(
                f"{factor['score']:.1f}×{factor['effective_weight']*100:.0f}%={factor['contribution']:.1f}"
                for factor in factor_scores.values() if factor["available"]
            ) + (f" = {industry_score:.1f}" if industry_score is not None else ""),
            "risk_formula": "市场拥挤代理 = 3个月动量×40% + 上涨广度×30% + 距52周高点×30%。",
            "risk_calculation": " + ".join(
                f"{item['score']:.1f}×{item['effective_weight']*100:.0f}%={item['contribution']:.1f}"
                for item in risk_details if item.get("score") is not None
            ) + (f" = {risk_score:.1f}" if risk_score is not None else ""),
            "normalisation": "所有异量纲原始值按预先公开的锚点线性映射到0–100并截尾；不使用当期样本的min-max，避免样本变化导致历史分数漂移。",
            "missing_policy": "缺失值不填0、不默认50；在同一因子内仅对可用子因子重新归一权重，并披露缺失项。",
            "method_reference": {
                "name": "OECD / EC-JRC — Handbook on Constructing Composite Indicators",
                "url": "https://doi.org/10.1787/9789264043466-en",
            },
        },
        "stage_decision": {
            "evaluation_order": "数据充足性 → 周期调整触发 → 市场拥挤警戒 → 商业化兑现 → 基建扩张 → 技术验证",
            "matched_stage": stage_id,
            "matched_rule": next((item["rule"] for item in stage_checks if item["stage_id"] == stage_id), ""),
            "checks": stage_checks,
            "deterioration_trigger_count": deterioration_count,
            "deterioration_required": 2,
            "deterioration_triggers": triggers,
        },
        "limitations": "已补充多公司商业化、企业采用与两期CAPEX数据，但统一模型能力基准、可比Token真实用量、机构级Forward估值与ETF申赎仍未接入。指数用于产业阶段监测与研究复核，不直接生成仓位。",
        "insufficient_data": not sufficient_industry_data,
        "sample_based": any(p.get("confidence") == "sample" for p in pricing_with_value),
        "missing_based": not sufficient_industry_data,
        "missing_factor_count": 3 - len(available_factors),
        "missing_component_count": missing_components,
        "data_coverage": {
            "pricing_records": len(pricing_with_value),
            "pricing_real": len(real_pricing),
            "business_records": len(business_with_value),
            "business_real": len(real_business),
            "gpu_real": len(real_gpu),
            "capex_real": len(real_capex),
            "capex_growth_companies": capex_growth_companies,
            "sources_ok": sources_ok,
            "sources_total": total_sources,
        },
        "stages_reference": stages,
    }


def _determine_stage(
    industry: float, risk: float, stages: list[dict[str, Any]], adjustment_trigger_count: int = 0
) -> tuple[str, str]:
    """Apply stage rules in explicit priority order."""
    if adjustment_trigger_count >= 2:
        return ("cyclical_adjustment", "周期调整期")
    if industry < 35:
        return ("tech_validation", "技术验证期")
    if risk >= 70 and industry >= 55:
        return ("valuation_crowding", "估值拥挤期")
    if industry >= 55:
        return ("commercialization", "商业化兑现期")
    return ("infra_expansion", "基础设施扩张期")


def _kpi_summary(
    pricing: list[dict[str, Any]], business: list[dict[str, Any]]
) -> dict[str, Any]:
    """生成总览页的 KPI 摘要文本。"""
    real = [p for p in pricing if p.get("confidence") != "sample" and p.get("value") is not None]
    cheapest = None
    if real:
        cheapest = min(real, key=lambda r: r.get("blended_cost_usd") or 999)
    return {
        "total_models_tracked": len(pricing),
        "models_with_real_data": len(real),
        "cheapest_model": cheapest.get("metric_name") if cheapest else None,
        "cheapest_cost_usd": cheapest.get("blended_cost_usd") if cheapest else None,
        "arr_records": len([b for b in business if b.get("value") is not None]),
        "data_freshness": "low" if len(real) < 5 else "moderate",
    }


# ── main ──────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    build_dashboard(root, verbose=args.verbose)
    print(f"[build_dashboard] 完成 → data/automated/dashboard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
