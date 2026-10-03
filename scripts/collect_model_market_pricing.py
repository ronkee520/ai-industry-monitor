#!/usr/bin/env python3
"""Collect an indicative, no-key model price snapshot from OpenRouter.

The output is deliberately labelled T3/aggregator_snapshot. Verified manual
vendor prices always take precedence in build_dashboard.py.
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


def collect_model_market_pricing(root: Path, *, dry_run: bool = False, verbose: bool = False) -> dict[str, Any]:
    cfg = _shared.load_json(root / "config" / "automated_sources.json", {}).get("model_market", {})
    routes = cfg.get("routes", {})
    if dry_run:
        return {"collector": "model_market_pricing", "status": "dry_run", "models": len(routes)}
    result = _shared.fetch_url(cfg.get("url", ""), user_agent="AI-Industry-Monitor/1.0 research dashboard")
    if not result.get("ok"):
        return {"collector": "model_market_pricing", "status": "partial", "error": result.get("error"), "records": 0}
    try:
        catalog = {item["id"]: item for item in json.loads(result["text"]).get("data", [])}
    except (ValueError, TypeError, KeyError) as exc:
        return {"collector": "model_market_pricing", "status": "error", "error": f"invalid_catalog: {exc}", "records": 0}

    models = {m["id"]: m for m in _shared.load_json(root / "config" / "models.json", {}).get("models", [])}
    companies = {c["id"]: c for c in _shared.load_json(root / "config" / "companies.json", {}).get("companies", [])}
    now = _shared.now_shanghai().isoformat(timespec="seconds")
    today = now[:10]
    records = []
    unmatched = []
    for model_id, candidates in routes.items():
        match = next((catalog[c] for c in candidates if c in catalog), None)
        if not match:
            unmatched.append(model_id)
            continue
        pricing = match.get("pricing", {})
        try:
            inp = float(pricing["prompt"]) * 1_000_000
            out = float(pricing["completion"]) * 1_000_000
        except (KeyError, TypeError, ValueError):
            unmatched.append(model_id)
            continue
        if inp < 0 or out < 0:
            unmatched.append(model_id)
            continue
        model = models.get(model_id, {})
        company_id = model.get("company_id")
        company = companies.get(company_id, {})
        cached = pricing.get("input_cache_read")
        cached_per_m = float(cached) * 1_000_000 if cached not in (None, "") else None
        blended = _shared.blended_cost(inp, out)
        records.append({
            "metric_id": f"token_blended_cost::{company_id}::{model_id}::market_route",
            "metric_name": f"{model.get('name', model_id)} 路由市场混合成本",
            "metric_category": "token_pricing",
            "value": blended,
            "input_per_m": round(inp, 6), "output_per_m": round(out, 6),
            "cached_input_per_m": round(cached_per_m, 6) if cached_per_m is not None else None,
            "unit": "USD_per_1M_tokens", "currency": "USD",
            "company_id": company_id, "model_id": model_id,
            "region": company.get("region", "global"), "tier": "aggregator_route",
            "period": today, "as_of_date": today, "collected_at": now,
            "source_name": cfg.get("source_name", "OpenRouter public model catalog"),
            "source_url": cfg.get("url"), "source_tier": 3,
            "evidence_status": "aggregator_snapshot", "confidence": "inferred",
            "context_window_k": round((match.get("context_length") or 0) / 1000, 1) or None,
            "provider_model_id": match.get("id"),
            "note": "公开路由市场快照；可能包含托管方加价或补贴，不等同于模型厂商直连官方价。",
            "tags": ["automated", "aggregator", "indicative"]
        })
    payload = {"generated_at": now, "source": cfg.get("url"), "records": records, "unmatched_model_ids": unmatched}
    _shared.atomic_write(root / "data" / "automated" / "model_market_pricing.json", payload)
    if verbose:
        print(f"[model_market_pricing] {len(records)} records, {len(unmatched)} unmatched")
    return {"collector": "model_market_pricing", "status": "ok" if records else "partial", "records": len(records), "unmatched": len(unmatched)}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=None); p.add_argument("--dry-run", action="store_true"); p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    a = parse_args(); root = _shared.resolve_project_root(a.project_root)
    print(json.dumps(collect_model_market_pricing(root, dry_run=a.dry_run, verbose=a.verbose), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
