"""IEC webstore publication 頁面的版本資料抓取與比對。

設計依據見 `active/1-iec-publication-version-checker/plan_README.md` D2 / D4。

要點：
- 版本資料內嵌在 HTML 的 Alpine.js `x-data` 工廠函式 return 字面量裡，
  形如 `lifecycles: {...}` / `underDevelopmentProduct: {...}`。
  服務端 HTML 內**沒有** ld+json 元素（那是前端 JS 動態注入的），故不可從那裡取。
- 用大括號配對掃出完整 JSON，不用 regex（JSON 內含巢狀 `{}`，regex 會斷在第一個 `}`）。
- `lifecycles` 解析不到 = 失敗，**不可**靜默當成「沒有更新」。
  `underDevelopmentProduct` 缺席是合法的（代表目前沒有開發中版本）。
"""

from __future__ import annotations

import html as html_mod
import json
from datetime import datetime, timezone

import requests

DEFAULT_URL = "https://webstore.iec.ch/en/publication/85813"
USER_AGENT = "smalldick-iec-version-checker/1.0 (+https://smalldick.etbiss.com)"
FETCH_TIMEOUT = 30


class FetchError(Exception):
    """抓取失敗（連線 / 逾時 / 非 200）。"""


class ParseError(Exception):
    """抓到了但解析不出版本資料 —— 通常代表目標頁面結構改變。"""


def fetch_html(url: str = DEFAULT_URL, timeout: int = FETCH_TIMEOUT) -> str:
    """GET 目標頁，回傳 HTML 文字。失敗一律拋 FetchError。"""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
    except requests.RequestException as exc:
        raise FetchError(f"連線失敗：{exc}") from exc

    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}（預期 200）")
    return resp.text


def _grab_object(text: str, key: str) -> str | None:
    """從 `<key>: {` 起，用大括號配對掃出完整的 JSON 物件字串。找不到回 None。"""
    marker = key + ": {"
    start = text.find(marker)
    if start < 0:
        return None

    open_idx = text.find("{", start)
    depth = 0
    in_string = False
    escaped = False

    for i in range(open_idx, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
    return None


def extract_blocks(html: str) -> dict:
    """取出 lifecycles（必要）與 underDevelopmentProduct（可缺）。

    lifecycles 缺席 / 解析失敗 / 空 dict → ParseError。
    """
    raw_lifecycles = _grab_object(html, "lifecycles")
    if raw_lifecycles is None:
        raise ParseError("頁面內找不到 lifecycles 區塊（目標頁面結構可能已改變）")
    try:
        lifecycles = json.loads(html_mod.unescape(raw_lifecycles))
    except json.JSONDecodeError as exc:
        raise ParseError(f"lifecycles 解析失敗：{exc}") from exc
    if not isinstance(lifecycles, dict) or not lifecycles:
        raise ParseError("lifecycles 為空或格式非預期")

    under = None
    raw_under = _grab_object(html, "underDevelopmentProduct")
    if raw_under is not None:
        try:
            parsed = json.loads(html_mod.unescape(raw_under))
        except json.JSONDecodeError:
            parsed = None
        # 空物件視為「沒有開發中版本」，與缺席同義。
        if isinstance(parsed, dict) and parsed:
            under = parsed

    return {"lifecycles": lifecycles, "under_development": under}


def _edition_sort_key(entry: dict) -> tuple:
    """排序用：先看 edition 數值，再看發布日期。無法解析的排最後面。"""
    main = entry.get("main") or {}
    try:
        edition = float(main.get("edition") or 0)
    except (TypeError, ValueError):
        edition = 0.0
    return (edition, str(main.get("publication_date") or ""))


def normalize(blocks: dict, *, source_url: str = DEFAULT_URL) -> dict:
    """把抓到的原始 JSON 正規化成穩定、可直接比對的 snapshot。

    穩定 = 欄位固定、list 排序固定 → 同樣的頁面永遠產出同樣的結構，
    比對時不會因為 dict 順序抖動而誤報「有更新」。
    """
    lifecycles = blocks["lifecycles"]

    entries = []
    for key, value in lifecycles.items():
        main = (value or {}).get("main") or {}
        entries.append(
            {
                "key": key,
                "reference": main.get("reference"),
                "edition": main.get("edition"),
                "publication_date": main.get("publication_date"),
                "status": main.get("status"),
            }
        )
    entries.sort(key=lambda e: (e["edition"] or "", e["publication_date"] or ""))

    latest = max(lifecycles.values(), key=_edition_sort_key, default=None)
    latest_main = (latest or {}).get("main") or {}

    under = blocks.get("under_development")
    under_norm = None
    if under:
        under_norm = {
            "reference": under.get("reference"),
            "edition": under.get("edition"),
            "stage": under.get("stage"),
            "status": under.get("status"),
            "forecast_pub_date": under.get("forecast_pub_date"),
        }

    return {
        "source_url": source_url,
        "current_reference": latest_main.get("reference"),
        "current_edition": latest_main.get("edition"),
        "current_publication_date": latest_main.get("publication_date"),
        "lifecycle_entries": entries,
        "under_development": under_norm,
    }


# 參與比對的欄位。checked_at 刻意排除 —— 它每次都不同，比了就永遠「有更新」。
COMPARED_FIELDS = (
    "current_reference",
    "current_edition",
    "current_publication_date",
    "lifecycle_entries",
    "under_development",
)

FIELD_LABELS = {
    "current_reference": "目前標準編號",
    "current_edition": "目前版次",
    "current_publication_date": "目前發布日",
    "lifecycle_entries": "版次歷史",
    "under_development": "開發中版本",
}


def diff(baseline: dict | None, current: dict) -> list[dict]:
    """逐欄比對，回傳有變動的欄位清單。baseline 為 None 時回空 list。"""
    if not baseline:
        return []

    changes = []
    for field in COMPARED_FIELDS:
        before = baseline.get(field)
        after = current.get(field)
        if before != after:
            changes.append(
                {
                    "field": field,
                    "label": FIELD_LABELS.get(field, field),
                    "before": before,
                    "after": after,
                }
            )
    return changes


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
