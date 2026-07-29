#!/usr/bin/env python3
"""AI Industry Monitor — AI 产业新闻采集器。

通过 Google News RSS 搜索 AI 商业化/Token/GPU/Capex 相关新闻。
新闻只进入待复核池 (data/news/ai_news_queue.json)。
新闻不自动写入正式指标。

单独运行:
    python scripts/collect_news.py --project-root .
    python scripts/collect_news.py --project-root . --dry-run --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from scripts import _shared  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 产业新闻采集器")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-per-query", type=int, default=10, help="每个查询最多保留条数")
    return parser.parse_args()


def log(msg: str, *, force: bool = False, verbose: bool = False) -> None:
    if force or verbose:
        print(f"[news] {msg}")


def collect_news(
    root: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    max_per_query: int = 10,
) -> dict[str, Any]:
    """从 Google News RSS 搜索 AI 相关新闻。"""
    sources_cfg = _shared.load_json(root / "config" / "sources.json", {})
    news_sources: list[dict[str, Any]] = sources_cfg.get("news_sources", [])
    if not news_sources:
        log("未配置新闻源，跳过", force=True)
        return {"status": "skipped", "reason": "no_news_sources", "fetched": 0}

    # dry-run 模式：不访问网络
    if dry_run:
        log(f"[DRY-RUN] 将查询 {len(news_sources)} 个新闻源（不访问网络）", force=True)
        return {
            "collector": "news", "queries": len(news_sources),
            "fetched": 0, "status": "dry_run", "dry_run": True,
        }

    now = _shared.now_shanghai()
    all_items: list[dict[str, Any]] = []

    for src in news_sources:
        if not src.get("enabled", True):
            continue
        try:
            items = _fetch_news_query(src, max_per_query, now)
            all_items.extend(items)
            log(f"  {src['id']}: {len(items)} 条", verbose=verbose)
        except Exception as exc:
            log(f"  {src['id']}: 失败 — {type(exc).__name__}: {exc}", force=True)

    # 按 URL 去重
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in sorted(all_items, key=lambda x: x.get("published_at", ""), reverse=True):
        url = item.get("url", "")
        if url and url in seen:
            continue
        seen.add(url)
        # 计算指纹用于后续变化检测
        item["content_hash"] = _shared.hash_content(
            f"{item.get('title','')} {item.get('publisher','')}"
        )
        deduped.append(item)

    total = len(deduped)
    log(f"收集 {total} 条（去重后）", force=True)

    summary: dict[str, Any] = {
        "collector": "news",
        "queries": len(news_sources),
        "fetched": total,
        "status": "ok" if total > 0 else "empty",
    }

    # dry_run 已在上方提前返回，此处必然是 dry_run=False
    queue_path = root / "data" / "news" / "ai_news_queue.json"
    existing = _shared.load_json(queue_path, [])
    merged: dict[str, dict[str, Any]] = {}
    for item in existing:
        if item.get("url"):
            merged[item["url"]] = item
    for item in deduped:
        merged[item["url"]] = item
    queue = sorted(merged.values(), key=lambda x: x.get("published_at", ""), reverse=True)[:200]
    _shared.atomic_write(queue_path, queue)
    log(f"ai_news_queue.json 已写入 ({len(queue)} 条)", force=True)

    hist_path = root / "data" / "news" / "news_history.jsonl"
    for item in deduped:
        _shared.append_jsonl(hist_path, {
            "collected_at": now.isoformat(timespec="seconds"),
            "url": item.get("url"), "title": item.get("title"),
            "publisher": item.get("publisher"), "published_at": item.get("published_at"),
            "query": item.get("query"),
        })

    return summary


def _fetch_news_query(
    src: dict[str, Any], max_items: int, now: datetime
) -> list[dict[str, Any]]:
    """抓取单个 Google News RSS 查询。"""
    q = src["query"]
    lang = src.get("language", "en-US")
    region = src.get("region", "US")
    ceid = f"{region}:{lang.split('-')[0]}"

    rss_url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({"q": q, "hl": lang, "gl": region, "ceid": ceid})
    )
    result = _shared.fetch_url(rss_url, timeout=15)

    if not result["ok"] or not result["text"]:
        return []

    items: list[dict[str, Any]] = []
    try:
        root_el = ET.fromstring(result["text"])
        for item_el in root_el.findall("./channel/item")[:max_items]:
            title = (item_el.findtext("title") or "").strip()
            link = (item_el.findtext("link") or "").strip()
            pub_date = (item_el.findtext("pubDate") or "").strip()
            source_el = item_el.find("source")
            publisher = (source_el.text or "").strip() if source_el is not None else ""

            published = _parse_pubdate(pub_date, now)
            items.append({
                "title": title,
                "url": link,
                "publisher": publisher or src["name"],
                "published_at": published,
                "collected_at": now.isoformat(timespec="seconds"),
                "query": q,
                "feed_id": src["id"],
                "feed_name": src["name"],
                "feed_tier": int(src.get("tier", 3)),
                "status": "pending_review",
                "tags": ["news", "rss"],
            })
    except ET.ParseError:
        pass

    return items


def _parse_pubdate(raw: str, fallback: datetime) -> str:
    """尝试解析 RSS pubDate 格式。"""
    if not raw:
        return fallback.isoformat()
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(_shared.CN_TZ).isoformat()
    except Exception:
        return fallback.isoformat()


def main() -> int:
    args = parse_args()
    root = _shared.resolve_project_root(args.project_root)
    result = collect_news(root, dry_run=args.dry_run, verbose=args.verbose,
                          max_per_query=args.max_per_query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
