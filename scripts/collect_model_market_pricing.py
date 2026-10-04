#!/usr/bin/env python3
"""Collect an indicative, no-key model price snapshot from OpenRouter.

The output is deliberately labelled T3/aggregator_snapshot. Verified manual
vendor prices always take precedence in build_dashboard.py.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))
from scripts import _shared  # noqa: E402


def _as_price(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _price_pair(value: Any) -> tuple[float, float] | None:
    parts = str(value or "").strip().split("/")
    if len(parts) != 2:
        return None
    inp, out = _as_price(parts[0]), _as_price(parts[1])
    return (inp, out) if inp is not None and out is not None else None


def _exact_history_rows(rows: list[dict[str, str]], provider_model_id: str) -> list[dict[str, str]]:
    """Return the archive stream for exactly one standard OpenRouter route.

    Prefer OpenRouter's own diff stream. LiteLLM's OpenRouter mirror is only a
    fallback for models whose price never changed in the primary stream.
    Batch/free/dated variants are deliberately excluded.
    """
    primary = [
        row for row in rows
        if row.get("source") == "openrouter" and row.get("model") == provider_model_id
    ]
    mirror_id = f"openrouter/{provider_model_id}"
    mirror = [
        row for row in rows
        if row.get("source") == "litellm" and row.get("model") == mirror_id
    ]
    useful_primary = any(
        _price_pair(row.get("new")) or row.get("field") in {"input_usd_per_mtok", "output_usd_per_mtok"}
        for row in primary
    )
    return primary if useful_primary else mirror


def build_market_price_history(
    records: list[dict[str, Any]],
    csv_text: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct daily route prices from the public append-only diff log.

    A day without a diff carries forward the latest observed price. This is an
    interval reconstruction, not synthetic price movement: the underlying
    archive is produced by comparing daily catalog snapshots.
    """
    archive_rows = list(csv.DictReader(io.StringIO(csv_text)))
    started = date.fromisoformat(cfg.get("history_started_at", "2026-07-28"))
    source_url = cfg.get("history_url")
    source_name = cfg.get("history_source_name", "OpenRouter daily price-change archive")
    output: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []

    for record in records:
        provider_id = record.get("provider_model_id")
        if not provider_id:
            continue
        rows = _exact_history_rows(archive_rows, provider_id)
        rows = sorted(rows, key=lambda row: row.get("date", ""))
        if not rows:
            # No exact archive evidence: leave coverage to a verified official
            # effective-price event rather than backdating today's route quote.
            continue
        by_date: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row.get("date"):
                by_date[row["date"]].append(row)

        # The first `old` value is the observed state immediately before the
        # first change. If no price change exists, the current live catalog
        # price is valid throughout the no-change interval.
        inp = next((v for row in rows if (v := _as_price(row.get("old"))) is not None
                    and row.get("field") == "input_usd_per_mtok"), None)
        out = next((v for row in rows if (v := _as_price(row.get("old"))) is not None
                    and row.get("field") == "output_usd_per_mtok"), None)
        first_pair = next((_price_pair(row.get("new")) for row in rows if _price_pair(row.get("new"))), None)
        if inp is None and first_pair:
            inp = first_pair[0]
        if out is None and first_pair:
            out = first_pair[1]
        if inp is None:
            inp = _as_price(record.get("input_per_m"))
        if out is None:
            out = _as_price(record.get("output_per_m"))
        if inp is None or out is None:
            continue

        first_evidence = min(by_date) if by_date else record.get("as_of_date")
        start = started
        # When the primary archive explicitly records a new route, do not
        # extend that route to dates before it existed.
        added_dates = [
            date.fromisoformat(row["date"]) for row in rows
            if row.get("source") == "openrouter" and row.get("event") == "added" and row.get("date")
        ]
        if added_dates:
            start = max(start, min(added_dates))
        elif rows and all(row.get("source") != "openrouter" for row in rows):
            # Mirror-only history proves the route no later than its first
            # observation, but not before it.
            start = max(start, date.fromisoformat(first_evidence))

        end = date.fromisoformat(record.get("as_of_date") or _shared.now_shanghai().date().isoformat())
        if end < start:
            start = end
        cursor = start
        count = 0
        while cursor <= end:
            day = cursor.isoformat()
            price_changed = False
            for event in by_date.get(day, []):
                pair = _price_pair(event.get("new"))
                if event.get("event") == "added" and pair:
                    inp, out = pair
                    price_changed = True
                field = event.get("field")
                new_value = _as_price(event.get("new"))
                if field == "input_usd_per_mtok" and new_value is not None:
                    inp = new_value
                    price_changed = True
                elif field == "output_usd_per_mtok" and new_value is not None:
                    out = new_value
                    price_changed = True

            # The live catalog is the authoritative final state for today.
            if cursor == end:
                current_inp = _as_price(record.get("input_per_m"))
                current_out = _as_price(record.get("output_per_m"))
                if current_inp is not None:
                    inp = current_inp
                if current_out is not None:
                    out = current_out
            blended = _shared.blended_cost(inp, out)
            output.append({
                "date": day,
                "metric_id": record["metric_id"],
                "value": blended,
                "blended_cost_usd": blended,
                "input_per_m": round(inp, 9),
                "output_per_m": round(out, 9),
                "currency": "USD",
                "event_type": "archived_price_change" if price_changed else "archived_price_interval",
                "provider_model_id": provider_id,
                "source_name": source_name,
                "source_url": source_url,
                "source_tier": 3,
                "evidence_status": "public_price_archive",
                "note": "由每日公开价格变更日志重建；无变更日延续最近一次已观测价格。",
            })
            count += 1
            cursor += timedelta(days=1)
        coverage.append({
            "metric_id": record["metric_id"],
            "provider_model_id": provider_id,
            "first_date": start.isoformat(),
            "last_date": end.isoformat(),
            "days": count,
            "archive_events": len(rows),
        })

    return {
        "generated_at": _shared.now_shanghai().isoformat(timespec="seconds"),
        "source": source_url,
        "method": "daily interval reconstruction from an append-only price-change log",
        "records": output,
        "coverage": coverage,
    }


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

    # Keep a small, automatically refreshed release radar alongside the curated
    # registry. This lets the product surface newly listed public models without
    # treating aggregator prices as official vendor prices.
    discovery_records = []
    excluded_tokens = (":free", ":batch", "image", "audio", "embedding", "moderation")
    for company_id, prefix in cfg.get("discovery_prefixes", {}).items():
        company = companies.get(company_id, {})
        candidates = []
        for item in catalog.values():
            provider_id = str(item.get("id", ""))
            if not provider_id.startswith(prefix) or any(token in provider_id.lower() for token in excluded_tokens):
                continue
            pricing = item.get("pricing", {})
            try:
                inp = float(pricing["prompt"]) * 1_000_000
                out = float(pricing["completion"]) * 1_000_000
            except (KeyError, TypeError, ValueError):
                continue
            if inp < 0 or out < 0:
                continue
            candidates.append((int(item.get("created") or 0), item, inp, out))

        for created, item, inp, out in sorted(candidates, key=lambda row: row[0], reverse=True)[:2]:
            pricing = item.get("pricing", {})
            cached = pricing.get("input_cache_read")
            try:
                cached_per_m = float(cached) * 1_000_000 if cached not in (None, "") else None
            except (TypeError, ValueError):
                cached_per_m = None
            released_at = datetime.fromtimestamp(created, timezone.utc).date().isoformat() if created else None
            discovery_records.append({
                "company_id": company_id,
                "company_name": company.get("name", company_id),
                "region": company.get("region", "global"),
                "name": item.get("name") or item.get("id"),
                "provider_model_id": item.get("id"),
                "released_at": released_at,
                "input_per_m": round(inp, 6),
                "output_per_m": round(out, 6),
                "cached_input_per_m": round(cached_per_m, 6) if cached_per_m is not None else None,
                "context_window_k": round((item.get("context_length") or 0) / 1000, 1) or None,
                "source_name": cfg.get("source_name", "OpenRouter public model catalog"),
                "source_url": cfg.get("url"),
                "source_tier": 3,
            })

    discovery_records.sort(key=lambda row: (row.get("released_at") or "", row.get("provider_model_id") or ""), reverse=True)
    payload = {
        "generated_at": now,
        "source": cfg.get("url"),
        "records": records,
        "discovery_records": discovery_records,
        "unmatched_model_ids": unmatched,
    }
    _shared.atomic_write(root / "data" / "automated" / "model_market_pricing.json", payload)
    history_status = "unavailable"
    history_records = 0
    history_result = _shared.fetch_url(
        cfg.get("history_url", ""),
        user_agent="AI-Industry-Monitor/1.0 research dashboard",
        max_bytes=2_000_000,
    )
    if history_result.get("ok"):
        history_payload = build_market_price_history(records, history_result.get("text") or "", cfg)
        _shared.atomic_write(root / "data" / "automated" / "model_market_price_history.json", history_payload)
        history_status = "ok"
        history_records = len(history_payload["records"])
    if verbose:
        print(f"[model_market_pricing] {len(records)} routed prices, {history_records} history rows, "
              f"{len(discovery_records)} discoveries, {len(unmatched)} unmatched")
    return {
        "collector": "model_market_pricing",
        "status": "ok" if records else "partial",
        "records": len(records),
        "discoveries": len(discovery_records),
        "unmatched": len(unmatched),
        "history_status": history_status,
        "history_records": history_records,
    }


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
