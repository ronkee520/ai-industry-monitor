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
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


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
    source_state = _shared.load_json(root / "data" / "automated" / "source_state.json", [])
    news_queue = _shared.load_json(root / "data" / "news" / "ai_news_queue.json", [])

    # 加载历史（用于计算 change_pct）
    price_history = _shared.read_jsonl(root / "data" / "history" / "token_pricing.jsonl")
    business_history = _shared.read_jsonl(root / "data" / "history" / "business.jsonl")

    # ── 1. Token 定价模块 ──
    pricing_records = _build_pricing(
        manual_pricing.get("records", []),
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

    # ── 3. Compute 模块（GPU + Capex） ──
    gpu_records = _build_gpu(root, company_by_id, today)

    # ── 4. 来源健康 ──
    source_status = _build_source_status(source_state, sources_cfg)
    health = _build_health(source_status, pricing_records, business_records, generated_at)

    # ── 5. AI Cycle 评分 ──
    cycle_scores = _build_cycle_scores(
        pricing_records, business_records, gpu_records,
        source_status, cycle_cfg, companies_list, generated_at,
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
            "schedule": "每周一、周五 09:00 (Asia/Shanghai)",
            "data_policy": "公开可引用数据。sample/missing/manual_required 标记明确。",
            "fx": {"cny_per_usd": fx, "note": "仅用于跨币种横向比较"},
        },
        "kpis": {
            "companies": company_count,
            "models_with_pricing": models_with_pricing,
            "source_ok": health["sources_ok"],
            "source_total": health["sources_total"],
            "arr_disclosures": arr_disclosed,
        },
        "overview": {
            "cycle": cycle_scores,
            "kpi_summary": _kpi_summary(pricing_records, business_records),
        },
        "token_pricing": {
            "records": pricing_records,
            "methodology": {
                "blended_formula": "input × 0.65 + output × 0.35 (USD)",
                "comparability": "不同币种按fx_rate转USD；Batch/缓存/长上下文/企业折扣不包含在内。",
            },
        },
        "business": {
            "records": business_records,
            "methodology": {
                "note": "ARR、年化收入、年度收入分开展示，不强行合并。未披露≠0。",
            },
        },
        "compute": {
            "gpu": gpu_records,
            "note": "GPU价格来自公开按需定价页。整机/合约/竞价价格不混排。",
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
             "blended_cost_usd": rec.get("blended_cost_usd")},
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
    _shared.append_jsonl(
        root / "data" / "history" / "cycle_scores.jsonl",
        {"date": snapshot_date, **cycle_scores},
        dedupe_keys=["date"],
    )

    if verbose:
        print(f"[build_dashboard] dashboard.json 已生成 ({len(pricing_records)} pricing + "
              f"{len(business_records)} business + {len(gpu_records)} gpu)")

    return payload


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
            inp = rec.get("input_per_m")
            out = rec.get("output_per_m")
            if inp is not None and out is not None:
                rec["blended_cost_usd"] = _shared.blended_cost(
                    float(inp), float(out),
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
    """构造 GPU 指标记录（第一期从 source_state 和 manual 组合）。"""
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
    generated_at: str,
) -> dict[str, Any]:
    """生成系统健康报告。"""
    ok = sum(1 for s in sources if s.get("status") == "ok")
    total = len(sources)
    missing_pricing = sum(1 for p in pricing if p.get("value") is None)
    missing_business = sum(1 for b in business if b.get("value") is None)
    sample_count = sum(1 for p in pricing if p.get("confidence") == "sample")

    return {
        "status": "ok" if ok > 0 else "partial",
        "generated_at": generated_at,
        "sources_ok": ok,
        "sources_total": total,
        "source_success_rate": f"{ok}/{total}" if total else "0/0",
        "pricing_total": len(pricing),
        "pricing_missing": missing_pricing,
        "pricing_sample": sample_count,
        "business_total": len(business),
        "business_missing": missing_business,
        "warnings": (
            [f"{missing_pricing} pricing records have null values"]
            if missing_pricing else []
        ) + (
            [f"{sample_count} pricing records are SAMPLES — do not cite as real data"]
            if sample_count else []
        ),
    }


# ── AI Cycle ──────────────────────────────────────────────────────

def _build_cycle_scores(
    pricing: list[dict[str, Any]],
    business: list[dict[str, Any]],
    gpu: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    cycle_cfg: dict[str, Any],
    companies: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """计算 AI 产业周期评分。

    第一期使用简化模式：大部分子因子依赖 manual 数据，
    此处仅建立评分结构框架。缺失因子标记为 insufficient_data。
    """
    factors = cycle_cfg.get("industry_factors", {})
    stages = cycle_cfg.get("stages", [])

    # ── 统计可用的数据覆盖度 ──
    pricing_with_value = [p for p in pricing if p.get("value") is not None]
    business_with_value = [b for b in business if b.get("value") is not None]
    sources_ok = sum(1 for s in sources if s.get("status") == "ok")

    # 简化评分：各因子 50 为中性起始点
    # 第一期不做精算，只输出框架
    tech_score = 50.0
    biz_score = 50.0
    capital_score = 50.0

    # 如果有真实 pricing 数据（不含 sample），微调 tech_score
    real_pricing = [p for p in pricing_with_value if p.get("confidence") != "sample"]
    if len(real_pricing) >= 5:
        tech_score = 55.0  # 有 ≥5 个真实价格，技术透明度中等偏上
    if len(real_pricing) >= 10:
        tech_score = 65.0

    # 如果有真实 business 数据，微调 biz_score
    real_business = [b for b in business_with_value if b.get("confidence") != "sample"]
    if len(real_business) >= 2:
        biz_score = 55.0
    if len(real_business) >= 5:
        biz_score = 65.0

    # 如果有 ≥50% 来源在线，capital_score 微调
    total_sources = len(sources)
    if total_sources > 0:
        if sources_ok / total_sources >= 0.5:
            capital_score = 55.0
        if sources_ok / total_sources >= 0.8:
            capital_score = 65.0

    industry_score = round(
        tech_score * factors.get("technology_maturity", {}).get("weight", 0.30)
        + biz_score * factors.get("commercialization", {}).get("weight", 0.35)
        + capital_score * factors.get("capital_investment", {}).get("weight", 0.35),
        1,
    )

    # Risk overlay — 第一期默认为 50 (中性)
    risk_score = 50.0
    risk_factors = cycle_cfg.get("risk_overlay", {}).get("sub_factors", {})
    risk_available = 0  # 第一期无自动化 risk 数据

    # 确定阶段
    stage_id, stage_label = _determine_stage(industry_score, risk_score, stages)

    missing_factors = 0
    if len(real_pricing) < 5:
        missing_factors += 1
    if len(real_business) < 2:
        missing_factors += 1

    return {
        "generated_at": generated_at,
        "stage_id": stage_id,
        "stage_label": stage_label,
        "industry_development_score": industry_score,
        "risk_crowding_score": risk_score if risk_available >= 2 else None,
        "risk_note": "第一期风险Overlay使用默认中性值(50)。第二期实现自动化后更新。" if risk_available < 2 else None,
        "factor_scores": {
            "technology_maturity": {"score": tech_score, "weight": 0.30},
            "commercialization": {"score": biz_score, "weight": 0.35},
            "capital_investment": {"score": capital_score, "weight": 0.35},
        },
        "confidence": "low" if missing_factors >= 2 else "medium",
        "insufficient_data": missing_factors >= 3,
        "sample_based": len(real_pricing) < 3,
        "missing_factor_count": missing_factors,
        "data_coverage": {
            "pricing_records": len(pricing_with_value),
            "pricing_real": len(real_pricing),
            "business_records": len(business_with_value),
            "business_real": len(real_business),
            "sources_ok": sources_ok,
            "sources_total": total_sources,
        },
        "stages_reference": stages,
    }


def _determine_stage(
    industry: float, risk: float, stages: list[dict[str, Any]]
) -> tuple[str, str]:
    """根据 industry_score 和 risk_score 判定周期阶段。"""
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
