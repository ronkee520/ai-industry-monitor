#!/usr/bin/env python3
"""Collect annual CAPEX and supply-chain fundamentals from SEC Companyfacts.

SEC's API is public and keyless. Set SEC_USER_AGENT to a descriptive value
including an email address for production use, e.g. "AI Monitor name@email".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))
from scripts import _shared  # noqa: E402

CAPEX_CONCEPTS = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
REVENUE_CONCEPTS = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")
GROSS_PROFIT_CONCEPTS = ("GrossProfit",)


def _annual_facts(companyfacts: dict[str, Any], concepts: tuple[str, ...], limit: int = 3) -> list[dict[str, Any]]:
    usgaap = companyfacts.get("facts", {}).get("us-gaap", {})
    entries: list[dict[str, Any]] = []
    for concept in concepts:
        units = usgaap.get(concept, {}).get("units", {}).get("USD", [])
        if units:
            entries = [x | {"concept": concept} for x in units]
            break
    candidates = []
    for x in entries:
        if x.get("form") not in ("10-K", "10-K/A") or x.get("fp") != "FY":
            continue
        try:
            duration = (date.fromisoformat(x["end"]) - date.fromisoformat(x["start"])).days
        except (KeyError, ValueError):
            continue
        if 300 <= duration <= 430 and isinstance(x.get("val"), (int, float)):
            candidates.append(x)
    # Restatements create duplicates. Keep the latest filed value for each fiscal end.
    by_end: dict[str, dict[str, Any]] = {}
    for x in sorted(candidates, key=lambda y: (y.get("end", ""), y.get("filed", ""))):
        by_end[x["end"]] = x
    return sorted(by_end.values(), key=lambda x: x["end"])[-limit:]


def collect_sec_fundamentals(root: Path, *, dry_run: bool = False, verbose: bool = False) -> dict[str, Any]:
    cfg = _shared.load_json(root / "config" / "automated_sources.json", {}).get("sec", {})
    companies_cfg = {c["id"]: c for c in _shared.load_json(root / "config" / "companies.json", {}).get("companies", [])}
    targets = cfg.get("companies", [])
    if dry_run:
        return {"collector": "sec_fundamentals", "status": "dry_run", "companies": len(targets)}
    ua = os.environ.get(cfg.get("user_agent_env", "SEC_USER_AGENT")) or "AI-Industry-Monitor/1.0 ronkee520@users.noreply.github.com"
    now = _shared.now_shanghai().isoformat(timespec="seconds")
    capex_records: list[dict[str, Any]] = []
    supply_records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for target in targets:
        cid, cik = target["company_id"], target["cik"]
        url = cfg.get("base_url", "").format(cik=cik)
        response = _shared.fetch_url(url, user_agent=ua, timeout=30, max_bytes=15_000_000)
        if not response.get("ok"):
            errors.append({"company_id": cid, "error": response.get("error", "fetch_failed")})
            continue
        try:
            facts = json.loads(response["text"])
        except (TypeError, ValueError) as exc:
            errors.append({"company_id": cid, "error": f"invalid_json: {exc}"})
            continue
        name = companies_cfg.get(cid, {}).get("name_zh", facts.get("entityName", cid))
        annual_capex = _annual_facts(facts, CAPEX_CONCEPTS)
        annual_revenue = _annual_facts(facts, REVENUE_CONCEPTS)
        annual_gp = {x["end"]: x for x in _annual_facts(facts, GROSS_PROFIT_CONCEPTS)}
        for x in annual_capex:
            value_b = round(x["val"] / 1_000_000_000, 3)
            fy = x.get("fy") or x["end"][:4]
            capex_records.append({
                "metric_id": f"capex_total::{cid}::fy{fy}", "metric_name": f"{name} FY{fy} CAPEX",
                "metric_category": "capex", "value": value_b, "unit": "USD_billion", "currency": "USD",
                "company_id": cid, "region": "overseas", "period": f"FY{fy}", "as_of_date": x["end"],
                "collected_at": now, "source_name": "SEC EDGAR Companyfacts", "source_url": url,
                "source_tier": 1, "evidence_status": "regulatory_filing", "confidence": "verified",
                "filing_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(x.get('accn','')).replace('-', '')}/",
                "xbrl_concept": x["concept"], "note": "SEC 10-K XBRL 年度购置物业、厂房及设备现金流；不同公司口径可能包含非AI投入。",
                "tags": ["automated", "sec", "capex", target.get("role", "")]
            })
        for x in annual_revenue:
            fy = x.get("fy") or x["end"][:4]
            value_b = round(x["val"] / 1_000_000_000, 3)
            gp = annual_gp.get(x["end"])
            supply_records.append({
                "metric_id": f"revenue::{cid}::fy{fy}", "metric_name": f"{name} FY{fy} 营收",
                "metric_category": "semiconductor" if target.get("role") == "semiconductor" else "cloud_financial",
                "value": value_b, "unit": "USD_billion", "currency": "USD", "company_id": cid,
                "region": "overseas", "period": f"FY{fy}", "as_of_date": x["end"], "collected_at": now,
                "source_name": "SEC EDGAR Companyfacts", "source_url": url, "source_tier": 1,
                "evidence_status": "regulatory_filing", "confidence": "verified", "xbrl_concept": x["concept"],
                "gross_profit_usd_b": round(gp["val"] / 1_000_000_000, 3) if gp else None,
                "gross_margin_pct": round(gp["val"] / x["val"] * 100, 1) if gp and x["val"] else None,
                "note": "SEC 10-K XBRL 年度公司整体营收；并非纯AI业务收入。", "tags": ["automated", "sec", target.get("role", "")]
            })
        if verbose:
            print(f"[sec] {cid}: {len(annual_capex)} capex, {len(annual_revenue)} revenue")
    payload = {"generated_at": now, "capex_records": capex_records, "supply_chain_records": supply_records, "errors": errors}
    output_path = root / "data" / "automated" / "sec_fundamentals.json"
    if capex_records or supply_records or not output_path.exists():
        _shared.atomic_write(output_path, payload)
    return {"collector": "sec_fundamentals", "status": "ok" if not errors else "partial", "companies": len(targets), "capex_records": len(capex_records), "supply_chain_records": len(supply_records), "errors": len(errors)}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(); p.add_argument("--project-root", default=None); p.add_argument("--dry-run", action="store_true"); p.add_argument("--verbose", action="store_true"); return p.parse_args()


def main() -> int:
    a = parse_args(); root = _shared.resolve_project_root(a.project_root)
    print(json.dumps(collect_sec_fundamentals(root, dry_run=a.dry_run, verbose=a.verbose), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
