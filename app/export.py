"""把「最近一次檢查版本」的結果組成可下載的 CSV。

設計依據見 `active/3-export-check-result-excel/plan_README.md` I5（落地 issue #3 D3 / D4 / D5）。

要點：
- **CSV，不是 .xlsx**（issue #3 D4）—— 標題的「Excel」理解為「用 Excel 開得起來」。
  ⛔ 不引入 `openpyxl` 之類的相依：只用 stdlib `csv` + `io`，映像不變大。
- **MUST 帶 UTF-8 BOM**（D4）—— 否則 Excel 開中文會亂碼。以 `utf-8-sig` 編碼達成。
- **四欄固定順序**（issue #3 `## UAT Checklist` 明列）：目標名稱 / 目標連結 / 最新版次 / 版次查詢結果。
- **一列一個來源**（v1 只有一個來源 → 只有一列）。欄位結構直接照多來源設計，
  未來加來源時只需 `sources.SOURCES` 多一筆、本模組不必改。
- **檢查失敗時「最新版次」欄寫失敗原因、⛔ 不留白**（D3），
  且**目標名稱 / 連結照樣有值**（D5：名稱不從抓取結果推導）。
- 逸出一律交給 `csv.writer` —— ⛔ 不手工拼字串（值裡有逗號 / 引號 / 換行時一定拼錯）。

本模組是**純函式層**：不碰 Flask、不碰檔案、⛔ 不碰網路。
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from . import sources

# ⛔ 順序即契約（issue #3 `## UAT Checklist`「四欄，順序為 …」）—— 改動順序等於改需求。
HEADERS: tuple[str, ...] = ("目標名稱", "目標連結", "最新版次", "版次查詢結果")

# 「版次查詢結果」欄的用語，與頁面上的結論用字一致（issue #3 UAT：「與網頁上顯示的結論一致」）。
VERDICTS = {
    "updated": "有更新",
    "no_update": "沒有更新",
    "error": "檢查失敗",
}

_EMPTY = "（無）"

# CSV 公式注入（formula injection）的起手字元。Excel 看到以這些字元開頭的儲存格會當成**公式**，
# 而本檔的內容有一部分來自**外部抓回來的頁面**（IEC 的 reference / edition 字串）。
# 本功能的整個重點就是「拿去 Excel 開」→ 這條路徑必須擋。
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def _neutralize(value: str) -> str:
    """讓儲存格永遠被 Excel 當成文字，⛔ 不當成公式。

    手法 = 前面加一個單引號（Excel 的「強制文字」前綴）。
    實務上本工具的四個欄位都不會以那些字元開頭（`IEC …` / `https://…` / `Edition …` /
    `抓取失敗：…`），所以**正常情況下這個函式什麼都不做** —— 它是為了目標頁面被改動 /
    被污染時的那一天而存在。
    """
    return "'" + value if value.startswith(_FORMULA_LEAD) else value


def _or_empty(value) -> str:
    return _EMPTY if value in (None, "") else str(value)


def _latest_version_cell(result: dict) -> str:
    """「最新版次」欄。

    檢查失敗 → **寫失敗原因**（D3，⛔ 不留白）。失敗訊息直接沿用 `main._fetch_snapshot()`
    產出的人話文案（`抓取失敗：…` / `解析失敗：…`）—— ⛔ 不另造一套，否則會與頁面上顯示的不一致。
    """
    if result.get("status") == "error":
        return result.get("message") or "檢查失敗（未提供原因）"

    snapshot = result.get("snapshot") or {}
    return "Edition {}（{}）・{}".format(
        _or_empty(snapshot.get("current_edition")),
        _or_empty(snapshot.get("current_publication_date")),
        _or_empty(snapshot.get("current_reference")),
    )


def _verdict_cell(result: dict) -> str:
    status = result.get("status")
    return VERDICTS.get(status, _or_empty(status))


def rows_from_check(result: dict, targets=None) -> list[dict[str, str]]:
    """把一次檢查結果攤成「一列一個來源」。

    v1 只有一個來源，故所有列共用同一份 result。未來多來源時，
    result 會變成 per-source（那時本函式的簽章要改，屬多來源票的範圍）。
    """
    targets = sources.SOURCES if targets is None else targets
    latest = _latest_version_cell(result)
    verdict = _verdict_cell(result)
    return [
        {
            HEADERS[0]: _neutralize(target["name"]),
            HEADERS[1]: _neutralize(target["url"]),
            HEADERS[2]: _neutralize(latest),
            HEADERS[3]: _neutralize(verdict),
        }
        for target in targets
    ]


def to_csv_bytes(rows: list[dict[str, str]]) -> bytes:
    """組出可直接回給瀏覽器的 CSV bytes。

    `utf-8-sig` = UTF-8 + BOM（D4 硬要求）。`\\r\\n` 是 CSV 慣例，Excel 最不容易出錯。
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(HEADERS), lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def filename_for(checked_at: str | None) -> str:
    """下載檔名。

    刻意用**純 ASCII** —— 中文檔名得處理 `Content-Disposition` 的 RFC 5987 編碼，
    對本工具沒有相稱的收益。
    """
    stamp = None
    if checked_at:
        try:
            stamp = datetime.fromisoformat(checked_at).strftime("%Y%m%d-%H%M%S")
        except ValueError:
            stamp = None
    return f"iec-check-{stamp or datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
