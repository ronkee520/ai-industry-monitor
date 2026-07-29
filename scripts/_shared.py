#!/usr/bin/env python3
"""AI Industry Monitor — 共享工具函数。

所有数据采集、构建脚本共用的基础设施。
仅使用 Python 3.10+ 标准库，零第三方依赖。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import tempfile
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── 常量 ──────────────────────────────────────────────────────────

CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; AI-Industry-Monitor/1.0; +https://github.com)"
)

VALID_REGIONS = {"overseas", "domestic", "global"}
VALID_SOURCE_TIERS = {1, 2, 3}
VALID_EVIDENCE_STATUSES = {
    "official_pricing",
    "company_disclosure",
    "media_report",
    "public_snapshot",
    "research_baseline",
    "estimate",
    "sample",
    "missing",
    "manual_required",
    "unknown",
}
VALID_CONFIDENCES = {
    "verified",
    "inferred",
    "reported",
    "sample",
    "stale_fallback",
    "missing",
}


# ── 项目根目录解析 ────────────────────────────────────────────────

def resolve_project_root(explicit: str | Path | None = None) -> Path:
    """解析项目根目录。

    优先使用传入的显式路径。
    若未传入，则基于当前文件位置推导：
    scripts/_shared.py → scripts/ 的父目录 = 项目根。

    Args:
        explicit: 显式指定的项目根路径。

    Returns:
        解析后的绝对 Path。
    """
    if explicit:
        root = Path(explicit).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"指定的项目根目录不存在: {root}")
        return root
    # 基于本文件位置推导: scripts/_shared.py → ..
    return Path(__file__).resolve().parent.parent


# ── JSON 读写 ─────────────────────────────────────────────────────

def load_json(path: Path, default: Any = None) -> Any:
    """安全读取 JSON 文件。

    文件不存在或 JSON 解析失败时返回 default，不抛出异常。

    Args:
        path: JSON 文件路径。
        default: 文件不存在或解析失败时的回退值。

    Returns:
        解析后的 Python 对象，或 default。
    """
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        import sys
        print(
            f"[WARNING] load_json failed for {path}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return default


def atomic_write(path: Path, data: Any, *, indent: int = 2) -> None:
    """原子写入 JSON 文件。

    先写入同目录下的临时文件，再 os.replace 到目标路径。
    保证写入过程不会产生损坏的半成品文件。

    Args:
        path: 目标 JSON 文件路径。
        data: 要写入的数据（需可 JSON 序列化）。
        indent: JSON 缩进空格数。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".tmp", prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
        os.replace(tmp_name, str(path))
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── JSON Lines 读写 ───────────────────────────────────────────────

def append_jsonl(
    path: Path,
    record: dict[str, Any],
    *,
    dedupe_keys: list[str] | None = None,
) -> None:
    """追加一行 JSON record 到 JSON Lines 文件。

    如果提供 dedupe_keys（如 ["date", "metric_id"]），则读取现有文件，
    若已存在同键记录则覆盖，否则追加。覆盖时重写整个文件以保证行级去重。

    Args:
        path: JSONL 文件路径。
        record: 要追加的 dict。
        dedupe_keys: 用于去重的键列表。None 表示直接追加不去重。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if dedupe_keys:
        _append_jsonl_with_dedup(path, record, dedupe_keys)
    else:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def _append_jsonl_with_dedup(
    path: Path, record: dict[str, Any], dedupe_keys: list[str]
) -> None:
    """读取 → 去重/更新 → 原子写回。"""
    existing = read_jsonl(path, skip_bad_lines=True)
    record_key = tuple(record.get(k) for k in dedupe_keys)

    replaced = False
    for i, row in enumerate(existing):
        row_key = tuple(row.get(k) for k in dedupe_keys)
        if row_key == record_key:
            existing[i] = record
            replaced = True
            break

    if not replaced:
        existing.append(record)

    # 原子写回
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".tmp", prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for row in existing:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_jsonl(path: Path, skip_bad_lines: bool = True) -> list[dict[str, Any]]:
    """读取 JSON Lines 文件，返回 list[dict]。

    Args:
        path: JSONL 文件路径。
        skip_bad_lines: True 时跳过无法解析的行（默认）。False 时抛出异常。

    Returns:
        解析后的 dict 列表。文件不存在时返回空列表。
    """
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                if isinstance(record, dict):
                    records.append(record)
            except json.JSONDecodeError:
                if skip_bad_lines:
                    import sys
                    print(
                        f"[WARNING] Skipping bad JSONL line {lineno} in {path}",
                        file=sys.stderr,
                    )
                    continue
                raise
    return records


# ── 时间工具 ──────────────────────────────────────────────────────

def now_shanghai() -> datetime:
    """返回当前北京时间（Asia/Shanghai, UTC+8）。"""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now(CN_TZ)


def today_shanghai() -> str:
    """返回当前北京日期，格式 YYYY-MM-DD。"""
    return now_shanghai().strftime("%Y-%m-%d")


# ── 哈希 ──────────────────────────────────────────────────────────

def hash_content(content: str) -> str:
    """返回文本内容的 SHA-256 指纹。

    用于检测网页内容是否变化。
    对内容做空白规范化后再哈希，降低微小格式差异的影响。

    Args:
        content: 文本内容。

    Returns:
        64 字符 hex 字符串。
    """
    normalized = re.sub(r"\s+", " ", content).strip()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()


# ── HTTP 请求 ─────────────────────────────────────────────────────

def fetch_url(
    url: str,
    *,
    timeout: int = 25,
    user_agent: str | None = None,
    max_bytes: int = 5_000_000,
) -> dict[str, Any]:
    """抓取单个 URL，返回结构化结果。

    抓取失败不抛出异常，而是返回包含 error 字段的 dict。

    Args:
        url: 目标 URL。
        timeout: 超时秒数。
        user_agent: User-Agent 头。默认使用项目 UA。
        max_bytes: 最大读取字节数。

    Returns:
        {
            "ok": bool,
            "status": int | None,
            "url": str,
            "final_url": str | None,
            "text": str | None,
            "content_hash": str | None,
            "text_chars": int | None,
            "error": str | None,
            "fetched_at": str (ISO 8601),
        }
    """
    fetched_at = now_shanghai().isoformat(timespec="seconds")
    result: dict[str, Any] = {
        "ok": False,
        "status": None,
        "url": url,
        "final_url": None,
        "text": None,
        "content_hash": None,
        "text_chars": None,
        "error": None,
        "fetched_at": fetched_at,
    }

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": user_agent or DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            },
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(max_bytes)
            content_type = resp.headers.get("Content-Type", "")
            final_url = resp.geturl()

            text = _decode_body(raw, content_type)
            result.update({
                "ok": True,
                "status": resp.status,
                "final_url": final_url,
                "text": text,
                "content_hash": hash_content(text),
                "text_chars": len(text),
            })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:400]

    return result


def _decode_body(raw: bytes, content_type: str) -> str:
    """尝试多种编码解码响应体。"""
    # 先从 Content-Type header 中提取 charset
    charset_match = re.search(r"charset=([\w-]+)", content_type, flags=re.I)
    candidates = [charset_match.group(1)] if charset_match else []
    candidates += ["utf-8", "gb18030", "gbk", "latin-1"]
    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


# ── Token 成本计算 ────────────────────────────────────────────────

def blended_cost(
    input_price: float | None,
    output_price: float | None,
    *,
    cached_input_price: float | None = None,
    input_weight: float = 0.65,
    output_weight: float = 0.35,
) -> float | None:
    """计算标准化 Token 混合成本。

    公式: input × input_weight + output × output_weight
    默认权重 65:35 近似典型对话负载比例。

    不包含缓存输入——缓存命中的成本显著低于标准输入，
    因此单独传入 cached_input_price 不参与此计算。

    Args:
        input_price: 输入价格 (per 1M tokens)。
        output_price: 输出价格 (per 1M tokens)。
        cached_input_price: 缓存输入价格（不参与计算，仅用于文档）。
        input_weight: 输入权重，默认 0.65。
        output_weight: 输出权重，默认 0.35。

    Returns:
        混合成本，或 None（当 input 或 output 缺失时）。
    """
    if input_price is None or output_price is None:
        return None
    return round(input_price * input_weight + output_price * output_weight, 6)


# ── 货币换算 ──────────────────────────────────────────────────────

def normalize_currency(
    value: float | None,
    currency: str,
    *,
    fx: dict[str, float] | None = None,
) -> float | None:
    """将非 USD 金额转为 USD。

    目前仅支持 CNY → USD 转换。USD 原值直接返回。
    不会默默猜汇率——如果需要转换但未提供 fx，则报错。

    Args:
        value: 原始金额。
        currency: "USD" 或 "CNY"。
        fx: 汇率字典，例如 {"CNY_per_USD": 7.25}。

    Returns:
        USD 金额，或 None（当 value 为 None 时）。

    Raises:
        ValueError: 需要 CNY→USD 转换但 fx 中缺少 cny_per_usd。
    """
    if value is None:
        return None
    currency_upper = currency.upper()
    if currency_upper == "USD":
        return value
    if currency_upper == "CNY":
        if fx is None or "cny_per_usd" not in fx:
            raise ValueError(
                "CNY→USD 转换需要提供 fx={'cny_per_usd': <rate>}，"
                f"当前 fx={fx}"
            )
        return round(value / fx["cny_per_usd"], 6)
    raise ValueError(f"不支持的币种: {currency}。当前支持: USD, CNY")


# ── 数据新鲜度 ────────────────────────────────────────────────────

def freshness(
    as_of_date: str | None,
    today: date | None = None,
) -> dict[str, Any]:
    """判定数据的新鲜程度。

    Args:
        as_of_date: ISO 日期字符串 (YYYY-MM-DD) 或 None。
        today: 参考日期，默认今天（北京时间）。

    Returns:
        {
            "status": "fresh" | "stale" | "very_stale" | "missing",
            "age_days": int | None,
        }

    Thresholds:
        - 0–14 days → fresh
        - 15–45 days → stale
        - >45 days → very_stale
        - as_of_date is None → missing
    """
    if as_of_date is None:
        return {"status": "missing", "age_days": None}

    if today is None:
        today = now_shanghai().date()

    try:
        data_date = date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        return {"status": "missing", "age_days": None}

    age = (today - data_date).days
    if age < 0:
        # 未来日期，当作 fresh（可能是时区差异）
        age = 0

    if age <= 14:
        return {"status": "fresh", "age_days": age}
    if age <= 45:
        return {"status": "stale", "age_days": age}
    return {"status": "very_stale", "age_days": age}


# ── 标准化指标构造 ────────────────────────────────────────────────

def normalized_metric(
    *,
    metric_id: str,
    metric_name: str,
    metric_category: str,
    value: float | None,
    unit: str,
    currency: str | None,
    company_id: str | None,
    model_id: str | None,
    region: str,
    period: str,
    as_of_date: str,
    collected_at: str | None,
    source_name: str,
    source_url: str,
    source_tier: int,
    evidence_status: str,
    confidence: str,
    note: str = "",
    secondary_value: float | None = None,
    tier: str | None = None,
    change_pct: float | None = None,
    change_abs: float | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """构造一条标准化的监测指标记录。

    参数完全对应 DESIGN.md 中定义的 Universal Metric Schema。

    Args:
        metric_id: 全局唯一标识，格式 {category}::{company}::{model}::{detail}。
        metric_name: 人类可读名称。
        metric_category: 指标大类。
        value: 主数值（可为 None，代表数据缺失）。
        unit: 标准化单位码。
        currency: USD | CNY | None。
        company_id: 关联公司 ID。
        model_id: 关联模型 ID。
        region: overseas | domestic | global。
        period: 数据所属期间（如 "2026-Q2"、"2026-07"）。
        as_of_date: 数据截至日期 (YYYY-MM-DD)。
        collected_at: 采集时间 ISO 8601，None 则使用当前时间。
        source_name: 人类可读来源名。
        source_url: 来源 URL。
        source_tier: 1-3。
        evidence_status: 证据状态枚举。
        confidence: 可信度枚举。
        note: 口径说明/上下文，必填。
        secondary_value: 辅助数值。
        tier: 产品/服务档位。
        change_pct: 环比变化百分比。
        change_abs: 环比变化绝对值。
        tags: 前端筛选标签。

    Returns:
        标准化指标 dict。

    Raises:
        ValueError: 枚举字段值不合法，或必需字段缺失。
    """
    # ── 必需字段检查 ──
    missing = []
    for field_name, field_val in [
        ("metric_id", metric_id),
        ("metric_name", metric_name),
        ("metric_category", metric_category),
        ("unit", unit),
        ("region", region),
        ("period", period),
        ("as_of_date", as_of_date),
        ("source_name", source_name),
        ("source_url", source_url),
        ("source_tier", source_tier),
        ("evidence_status", evidence_status),
        ("confidence", confidence),
        ("note", note),
    ]:
        if field_val is None or (isinstance(field_val, str) and not field_val.strip()):
            missing.append(field_name)
    if missing:
        raise ValueError(
            f"标准化指标缺少必需字段: {', '.join(missing)}"
        )

    # ── 枚举校验 ──
    if region not in VALID_REGIONS:
        raise ValueError(
            f"region='{region}' 不合法，允许值: {VALID_REGIONS}"
        )
    if source_tier not in VALID_SOURCE_TIERS:
        raise ValueError(
            f"source_tier={source_tier} 不合法，允许值: {VALID_SOURCE_TIERS}"
        )
    if evidence_status not in VALID_EVIDENCE_STATUSES:
        raise ValueError(
            f"evidence_status='{evidence_status}' 不合法，允许值: {VALID_EVIDENCE_STATUSES}"
        )
    if confidence not in VALID_CONFIDENCES:
        raise ValueError(
            f"confidence='{confidence}' 不合法，允许值: {VALID_CONFIDENCES}"
        )

    # ── 构造记录 ──
    if collected_at is None:
        collected_at = now_shanghai().isoformat(timespec="seconds")

    record: dict[str, Any] = {
        "metric_id": metric_id,
        "metric_name": metric_name,
        "metric_category": metric_category,
        "value": value,
        "secondary_value": secondary_value,
        "unit": unit,
        "currency": currency,
        "company_id": company_id,
        "model_id": model_id,
        "region": region,
        "tier": tier,
        "period": period,
        "as_of_date": as_of_date,
        "collected_at": collected_at,
        "source_name": source_name,
        "source_url": source_url,
        "source_tier": source_tier,
        "evidence_status": evidence_status,
        "confidence": confidence,
        "change_pct": change_pct,
        "change_abs": change_abs,
        "note": note,
        "tags": tags or [],
    }
    return record


# ── HTML 工具 ─────────────────────────────────────────────────────

def visible_text(html_document: str) -> str:
    """从 HTML 文档中提取可见文本。

    去除 script、style、svg、noscript 标签内容，
    合并空白字符，返回纯文本。

    Args:
        html_document: 原始 HTML 字符串。

    Returns:
        纯文本字符串。
    """
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() in {"script", "style", "svg", "noscript", "head"}:
                self.skip += 1

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() in {"script", "style", "svg", "noscript", "head"} and self.skip:
                self.skip -= 1

        def handle_data(self, data: str) -> None:
            if not self.skip:
                stripped = data.strip()
                if stripped:
                    self.parts.append(stripped)

    parser = _TextExtractor()
    parser.feed(html_document)
    from html import unescape
    text = " ".join(parser.parts)
    return re.sub(r"\s+", " ", unescape(text)).strip()
