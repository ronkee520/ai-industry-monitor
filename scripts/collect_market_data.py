#!/usr/bin/env python3
"""Collect keyless daily prices from Stooq for watchlist trend/risk signals."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import statistics
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))
from scripts import _shared  # noqa: E402


def _fetch_one(item: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    symbol = item["symbol"]
    from urllib.parse import quote
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=2y&interval=1d&events=div%2Csplits"
    response = _shared.fetch_url(url, user_agent="Mozilla/5.0 AI-Industry-Monitor/1.0", timeout=30)
    if not response.get("ok"):
        return None, response.get("error", "fetch_failed")
    try:
        chart = json.loads(response["text"])["chart"]["result"][0]
        timestamps = chart["timestamp"]
        closes = chart["indicators"].get("adjclose", chart["indicators"].get("quote"))[0]
        closes = closes.get("adjclose", closes.get("close", []))
        rows = [(dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat(), float(value))
                for ts, value in zip(timestamps, closes) if value is not None and float(value) > 0]
        currency = chart.get("meta", {}).get("currency")
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, f"invalid_chart_json: {exc}"
    if len(rows) < 20:
        return None, "insufficient_history"
    rows.sort()
    latest_date, latest = rows[-1]
    def ret(days: int) -> float | None:
        target = _shared.now_shanghai().date() - timedelta(days=days)
        prior = next(((d, v) for d, v in reversed(rows) if d <= target.isoformat()), None)
        return round((latest / prior[1] - 1) * 100, 2) if prior else None
    year_start = next(((d, v) for d, v in rows if d[:4] == latest_date[:4]), None)
    daily = [rows[i][1] / rows[i - 1][1] - 1 for i in range(max(1, len(rows) - 252), len(rows))]
    high_52w = max(v for _, v in rows[-252:])
    rec = {
        "symbol": symbol, "name": item.get("name"), "role": item.get("role"),
        "close": latest, "currency": currency or "local", "as_of_date": latest_date,
        "return_1w_pct": ret(7), "return_1m_pct": ret(30), "return_3m_pct": ret(91), "return_1y_pct": ret(365),
        "return_ytd_pct": round((latest / year_start[1] - 1) * 100, 2) if year_start else None,
        "drawdown_52w_pct": round((latest / high_52w - 1) * 100, 2),
        "volatility_1y_pct": round(statistics.stdev(daily) * math.sqrt(252) * 100, 1) if len(daily) > 2 else None,
        "source_name": "Yahoo Finance chart snapshot", "source_url": url, "source_tier": 3,
        "evidence_status": "market_snapshot", "confidence": "inferred",
        "note": "免费复权日线快照，适合趋势代理；正式投资决策应以交易所/持牌行情源复核。"
    }
    return rec, None


def collect_market_data(root: Path, *, dry_run: bool = False, verbose: bool = False) -> dict[str, Any]:
    watch = _shared.load_json(root / "config" / "watchlist.json", {})
    items = watch.get("foreign", []) + watch.get("domestic", [])
    if dry_run:
        return {"collector": "market_data", "status": "dry_run", "symbols": len(items)}
    records, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_one, item): item for item in items}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                rec, err = future.result()
            except Exception as exc:
                rec, err = None, f"{type(exc).__name__}: {exc}"
            if rec: records.append(rec)
            else: errors.append({"symbol": item["symbol"], "error": err})
    records.sort(key=lambda r: r["symbol"])
    payload = {"generated_at": _shared.now_shanghai().isoformat(timespec="seconds"), "records": records, "errors": errors}
    path = root / "data" / "automated" / "market.json"
    if records or not path.exists():
        _shared.atomic_write(path, payload)
    if verbose: print(f"[market] {len(records)} ok, {len(errors)} failed")
    return {"collector": "market_data", "status": "ok" if not errors else "partial", "records": len(records), "errors": len(errors)}


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser(); p.add_argument("--project-root",default=None); p.add_argument("--dry-run",action="store_true"); p.add_argument("--verbose",action="store_true"); return p.parse_args()


def main() -> int:
    a=parse_args(); root=_shared.resolve_project_root(a.project_root); print(json.dumps(collect_market_data(root,dry_run=a.dry_run,verbose=a.verbose),ensure_ascii=False,indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
