#!/usr/bin/env python3
"""AI Industry Monitor — 定价候选数据采集器。

从官方定价页尝试自动提取候选价格，输出到 pricing_candidates.json/.csv。
注意：所有输出标记为 candidate/needs_review，不直接写入正式 token_pricing.json。

用法:
    python scripts/collect_pricing_candidates.py --project-root . --dry-run
    python scripts/collect_pricing_candidates.py --project-root . --verbose
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
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


# ── 价格提取模式 ──────────────────────────────────────────────
PRICE_PATTERNS = [
    # "$2.50 / 1M tokens" 或 "$2.50 per million"
    re.compile(
        r'\$?\s*(\d+\.?\d*)\s*(?:USD|usd)?\s*/(?:1M|million|百万)\s*(?:tokens|token|input)?',
        re.IGNORECASE,
    ),
    # "input: $2.50" 或 "Input $2.50"
    re.compile(
        r'(?:input|输入)\s*:?\s*\$?\s*(\d+\.?\d*)\s*(?:USD|usd|/M|/百万)?',
        re.IGNORECASE,
    ),
    # "output: $10.00"
    re.compile(
        r'(?:output|输出)\s*:?\s*\$?\s*(\d+\.?\d*)\s*(?:USD|usd|/M|/百万)?',
        re.IGNORECASE,
    ),
    # CNY: "2.00 元/百万tokens"
    re.compile(
        r'(\d+\.?\d*)\s*元\s*/\s*(?:百万|1M)\s*(?:tokens|token)?',
    ),
    # Generic: a dollar amount near "per 1M"
    re.compile(
        r'\$(\d+\.?\d{1,4})\s*(?:per|/)\s*(?:1M|million)\s*(?:input|output)?\s*(?:tokens?)?',
        re.IGNORECASE,
    ),
]

JS_RENDERED_SIGNATURES = [
    # 页面主要靠 JS bundle
    (r'<div\s+id\s*=\s*"[^"]*"[^>]*>\s*</div>', 3),   # 大量空 div
    (r'<script[^>]*src\s*=\s*"[^"]*bundle[^"]*"', 5),   # bundle.js
    (r'__NEXT_DATA__|__NUXT__|window\.__INITIAL_STATE__', 5),  # Next/Nuxt SSR
    (r'function\s*\(\)\s*\{\s*["\']use strict["\']', 3),  # raw JS
    (r'<div\s+id\s*=\s*"root"[^>]*>\s*</div>', 4),  # React mount point
    (r'<div\s+id\s*=\s*"app"[^>]*>\s*</div>', 4),    # Vue mount point
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="定价候选数据采集器")
    p.add_argument("--project-root", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--timeout", type=int, default=20)
    return p.parse_args()


def log(msg: str, *, force: bool = False, verbose: bool = False) -> None:
    if force or verbose:
        print(f"[candidate] {msg}")


def collect_candidates(
    root: Path, *, dry_run: bool = False, verbose: bool = False, timeout: int = 20,
) -> list[dict[str, Any]]:
    """主逻辑：访问所有定价页，提取候选价格。"""
    # 加载模板（获取 source_url 映射）
    tmpl_path = root / "data" / "manual" / "manual_pricing_template.csv"
    if not tmpl_path.exists():
        log("模板文件不存在，跳过", force=True)
        return []

    tmpl_rows = _read_template(tmpl_path)
    log(f"加载 {len(tmpl_rows)} 个模型定价源", force=True)

    # 去重 source_url（同一个 URL 可能对应多个模型）
    url_to_models: dict[str, list[dict[str, str]]] = {}
    for row in tmpl_rows:
        url = (row.get("source_url") or "").strip()
        if url:
            url_to_models.setdefault(url, []).append(row)

    candidates: list[dict[str, Any]] = []

    if dry_run:
        log(f"[DRY-RUN] 将访问 {len(url_to_models)} 个定价页（不输出文件）", force=True)
        for url, models in url_to_models.items():
            for m in models:
                log(f"  {m['company_id']}::{m['model_id']} <- {url}", verbose=True)
        return []

    # 并发抓取
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(_shared.fetch_url, url, timeout=timeout): (url, models)
                for url, models in url_to_models.items()}
        for fut in concurrent.futures.as_completed(futs):
            url, models = futs[fut]
            try:
                result = fut.result()
            except Exception as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            for model_row in models:
                cand = _extract_candidate(model_row, result, url)
                candidates.append(cand)
                log(
                    f"  {cand['company_id']}::{cand['model_id']}: "
                    f"{cand['extraction_status']} conf={cand['confidence']}",
                    verbose=verbose,
                )

    # 写入文件
    if not dry_run:
        out_json = root / "data" / "manual" / "pricing_candidates.json"
        out_csv = root / "data" / "manual" / "pricing_candidates.csv"
        _shared.atomic_write(out_json, {
            "_description": "AI Industry Monitor — 自动提取的候选定价数据。需要人工核验。",
            "_note": "ALL VALUES ARE CANDIDATES. Do not cite as verified pricing until manually reviewed.",
            "generated_at": _shared.now_shanghai().isoformat(timespec="seconds"),
            "candidates": candidates,
        })
        _write_candidates_csv(out_csv, candidates)
        log(f"输出: {out_json.name} + {out_csv.name} ({len(candidates)} 条)", force=True)

    return candidates


def _read_template(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _extract_candidate(
    model_row: dict[str, str],
    result: dict[str, Any],
    url: str,
) -> dict[str, Any]:
    """从抓取结果中提取候选价格。"""
    cid = (model_row.get("company_id") or "").strip()
    mid = (model_row.get("model_id") or "").strip()
    mname = (model_row.get("model_name") or mid).strip()
    sname = (model_row.get("source_name") or "").strip()
    now = _shared.now_shanghai().isoformat(timespec="seconds")

    base: dict[str, Any] = {
        "company_id": cid,
        "model_id": mid,
        "model_name": mname,
        "source_url": url,
        "source_name": sname,
        "fetched_at": now,
        "extraction_status": "failed",
        "input_price_per_m_candidate": None,
        "output_price_per_m_candidate": None,
        "cached_input_price_per_m_candidate": None,
        "currency_candidate": None,
        "raw_text_snippet": "",
        "confidence": "failed",
        "reason": "",
        "manual_review_required": True,
    }

    if not result.get("ok"):
        base["reason"] = f"fetch failed: {result.get('error', 'unknown')}"
        base["extraction_status"] = "blocked" if "403" in (result.get("error") or "") else "failed"
        return base

    text = result.get("text", "")
    if not text or len(text) < 200:
        base["reason"] = "empty or very short response"
        base["extraction_status"] = "failed"
        return base

    # 检查是否为 JS 动态渲染
    js_score = _js_render_score(text)
    if js_score >= 10:
        base["reason"] = f"page appears to be JS-rendered (score={js_score}). HTML does not contain visible pricing. Manual review required."
        base["extraction_status"] = "js_rendered"
        base["raw_text_snippet"] = text[:300]
        return base

    # 转为可见文本
    visible = _shared.visible_text(text)

    # 查找模型名提及
    model_tokens = re.split(r'[-_\s]+', mid.lower())
    model_found = any(tok in visible.lower() for tok in model_tokens if len(tok) >= 2)

    # 提取可见文本中模型名附近的窗口
    snippet = visible[:3000]
    if model_found:
        # 找到模型名位置，取周围文本
        for tok in model_tokens:
            if len(tok) >= 2:
                idx = visible.lower().find(tok.lower())
                if idx >= 0:
                    start = max(0, idx - 500)
                    end = min(len(visible), idx + 2500)
                    snippet = visible[start:end]
                    break

    base["raw_text_snippet"] = snippet[:2000]

    # 搜索价格
    prices = _extract_prices(snippet)

    if not prices:
        base["reason"] = "no price patterns found in visible text"
        base["extraction_status"] = "ambiguous"
        base["confidence"] = "needs_review"
        return base

    # 填充候选价格
    inp = prices.get("input") or prices.get("generic")
    outp = prices.get("output")
    cached = prices.get("cached")

    if inp is not None:
        base["input_price_per_m_candidate"] = inp
    if outp is not None:
        base["output_price_per_m_candidate"] = outp
    if cached is not None:
        base["cached_input_price_per_m_candidate"] = cached

    # 判断币种
    if "CNY" in snippet or "¥" in snippet or "元" in snippet:
        base["currency_candidate"] = "CNY"
    else:
        base["currency_candidate"] = "USD"

    if inp is not None and outp is not None:
        base["extraction_status"] = "parsed"
        base["confidence"] = "candidate"
        base["reason"] = f"extracted input={inp}, output={outp} from visible text. Model name {'found' if model_found else 'NOT FOUND'} in page. MUST verify manually."
    elif inp is not None:
        base["extraction_status"] = "partial"
        base["confidence"] = "needs_review"
        base["reason"] = f"found input={inp} but no clear output price. May need manual extraction."
    else:
        base["extraction_status"] = "ambiguous"
        base["confidence"] = "needs_review"
        base["reason"] = "found price-like numbers but could not reliably assign to input/output."

    return base


def _js_render_score(html: str) -> int:
    """估算页面是否为 JS 动态渲染。高分 → 大概率 JS 渲染。"""
    score = 0
    for pattern, weight in JS_RENDERED_SIGNATURES:
        if re.search(pattern, html, re.IGNORECASE):
            score += weight
    # 可见文本很短 (< 500 chars) 也是强信号
    visible = _shared.visible_text(html)
    if len(visible) < 500:
        score += 8
    return score


def _extract_prices(text: str) -> dict[str, float | None]:
    """从可见文本中提取价格。"""
    result: dict[str, float | None] = {
        "input": None, "output": None, "cached": None, "generic": None,
    }
    all_numbers = re.findall(r'(?<!\w)\$?\s*(\d+\.?\d{0,4})\s*(?:USD|usd)?', text)
    numbers = [float(n) for n in all_numbers if 0.001 < float(n) < 1000.0]

    # 尝试匹配 input / output 标注
    # "input $2.50 / 1M tokens, output $10.00 / 1M tokens"
    input_patterns = [
        rf'(?:input|输入)\s*:?\s*\$?\s*{re.escape(str(n))}'
        for n in sorted(set(numbers), reverse=True)[:20]
    ]
    output_patterns = [
        rf'(?:output|输出)\s*:?\s*\$?\s*{re.escape(str(n))}'
        for n in sorted(set(numbers), reverse=True)[:20]
    ]

    for pat in input_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["input"] = float(re.search(r'(\d+\.?\d*)', m.group()).group(1))
            break
    for pat in output_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["output"] = float(re.search(r'(\d+\.?\d*)', m.group()).group(1))
            break

    # generic: 取第一个看起来像 token 价格的数字
    if not result["input"] and numbers:
        # 找 > 0.01 且 < 500 的数字（token价格典型范围）
        plausible = [n for n in numbers if 0.01 < n < 500]
        if plausible:
            result["generic"] = plausible[0]

    return result


def _write_candidates_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fields = [
        "company_id", "model_id", "model_name", "source_url", "source_name",
        "fetched_at", "extraction_status", "input_price_per_m_candidate",
        "output_price_per_m_candidate", "cached_input_price_per_m_candidate",
        "currency_candidate", "confidence", "reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for c in candidates:
            w.writerow(c)


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    candidates = collect_candidates(
        root, dry_run=args.dry_run, verbose=args.verbose, timeout=args.timeout,
    )
    statuses = {}
    for c in candidates:
        s = c["extraction_status"]
        statuses[s] = statuses.get(s, 0) + 1
    print(f"完成: {len(candidates)} 条, 状态分布: {statuses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
