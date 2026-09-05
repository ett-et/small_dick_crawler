"""CSV 匯出的純函式測試（issue #3 D3 / D4 / D5）—— ⛔ 不碰 HTTP、不連外網。"""

import csv
import io

from app import export, sources


def read_back(payload: bytes) -> list[list[str]]:
    """把匯出的 bytes 當成 Excel / csv 模組會怎麼讀它 —— 用 utf-8-sig 讀（BOM 會被吃掉）。"""
    return list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))


OK_RESULT = {
    "status": "no_update",
    "message": "沒有更新（與基準完全相同）",
    "checked_at": "2026-09-05T10:11:12+08:00",
    "snapshot": {
        "current_edition": "4.0",
        "current_publication_date": "2023-05-26",
        "current_reference": "IEC 62368-1:2023",
    },
}

ERR_RESULT = {
    "status": "error",
    "message": "抓取失敗：連線逾時",
    "checked_at": "2026-09-05T10:11:12+08:00",
}


def test_csv_starts_with_utf8_bom():
    """D4 硬要求：沒有 BOM 的話 Excel 開中文會亂碼。"""
    payload = export.to_csv_bytes(export.rows_from_check(OK_RESULT))
    assert payload.startswith(b"\xef\xbb\xbf"), "CSV MUST 帶 UTF-8 BOM（D4）"


def test_headers_are_four_columns_in_fixed_order():
    """順序即契約（issue #3 `## UAT Checklist`）。"""
    rows = read_back(export.to_csv_bytes(export.rows_from_check(OK_RESULT)))
    assert rows[0] == ["目標名稱", "目標連結", "最新版次", "版次查詢結果"]


def test_one_row_per_source():
    """一列一個來源 —— v1 只有一個來源 → 表頭 + 一列。"""
    rows = read_back(export.to_csv_bytes(export.rows_from_check(OK_RESULT)))
    assert len(rows) == 1 + len(sources.SOURCES) == 2

    # 結構要容得下多來源（issue #3：加來源不需重做）
    fake = ({"name": "A", "url": "https://a"}, {"name": "B", "url": "https://b"})
    two = read_back(export.to_csv_bytes(export.rows_from_check(OK_RESULT, fake)))
    assert len(two) == 3
    assert [r[0] for r in two[1:]] == ["A", "B"]


def test_values_with_separators_are_quoted():
    """值裡有逗號 / 引號 / 換行時 ⛔ 不得讓欄位錯位（逸出交給 csv 模組、不手拼字串）。"""
    nasty = ({"name": '有逗號, 有"引號"\n還有換行', "url": "https://x?a=1,2"},)
    payload = export.to_csv_bytes(export.rows_from_check(OK_RESULT, nasty))
    rows = read_back(payload)
    assert len(rows) == 2, "逸出正確的話仍然只有表頭 + 一列"
    assert rows[1][0] == '有逗號, 有"引號"\n還有換行'
    assert len(rows[1]) == 4, "欄位數不得因為值裡的逗號而變多"


def test_error_row_keeps_name_and_writes_reason():
    """D3：失敗時「最新版次」寫失敗原因、⛔ 不留白；D5：名稱與連結仍然有值。"""
    rows = read_back(export.to_csv_bytes(export.rows_from_check(ERR_RESULT)))
    name, url, latest, verdict = rows[1]

    assert name == sources.SOURCES[0]["name"] and name, "D5：失敗列照樣要有名字"
    assert url == sources.SOURCES[0]["url"] and url, "D5：失敗列照樣要有連結"
    assert latest == "抓取失敗：連線逾時", "D3：最新版次欄 MUST 寫失敗原因"
    assert latest.strip(), "D3：⛔ 不留白"
    assert verdict == "檢查失敗"


def test_error_without_message_still_not_blank():
    """訊息意外缺席時仍不得留白（D3 的下限）。"""
    rows = read_back(export.to_csv_bytes(export.rows_from_check({"status": "error"})))
    assert rows[1][2].strip(), "D3：任何情況下最新版次欄都不留白"


def test_verdict_matches_page_wording():
    """「版次查詢結果」用語與頁面上的結論一致（issue #3 UAT）。"""
    for status, expected in [("updated", "有更新"), ("no_update", "沒有更新"), ("error", "檢查失敗")]:
        rows = read_back(export.to_csv_bytes(export.rows_from_check({**OK_RESULT, "status": status})))
        assert rows[1][3] == expected


def test_success_row_shows_latest_version():
    rows = read_back(export.to_csv_bytes(export.rows_from_check(OK_RESULT)))
    latest = rows[1][2]
    assert "4.0" in latest and "2023-05-26" in latest and "IEC 62368-1:2023" in latest


def test_filename_is_ascii_and_csv():
    """檔名刻意純 ASCII —— 中文檔名要處理 Content-Disposition 的 RFC 5987 編碼。"""
    name = export.filename_for("2026-09-05T10:11:12+08:00")
    assert name == "iec-check-20260905-101112.csv"
    assert name.isascii()
    # 壞的 / 缺的時間戳不得炸掉下載
    assert export.filename_for("不是時間").endswith(".csv")
    assert export.filename_for(None).endswith(".csv")


def test_source_url_is_not_a_second_copy():
    """D5：網址的唯一定義仍是 `iec.DEFAULT_URL` —— ⛔ sources.py 不另打一份字串。"""
    from app import iec

    assert sources.SOURCES[0]["url"] is iec.DEFAULT_URL


def test_formula_injection_is_neutralized():
    """CSV 公式注入：本檔的內容有一部分來自**外部抓回來的頁面**，而本功能的重點就是拿去 Excel 開。

    以 `= + - @` 開頭的儲存格會被 Excel 當成公式執行 → 一律加單引號前綴強制成文字。
    """
    evil = ({"name": "=1+1", "url": "@SUM(A1)"},)
    rows = read_back(export.to_csv_bytes(export.rows_from_check({**OK_RESULT, "status": "error", "message": "-cmd|' /c calc'!A0"}, evil)))
    assert rows[1][0] == "'=1+1"
    assert rows[1][1] == "'@SUM(A1)"
    assert rows[1][2].startswith("'-"), "失敗原因欄同樣要中和"


def test_normal_values_are_untouched():
    """中和只在真的需要時發生 —— 正常值 ⛔ 不得被加上引號（會破壞 D5 的「與畫面完全一致」）。"""
    rows = read_back(export.to_csv_bytes(export.rows_from_check(OK_RESULT)))
    assert rows[1][0] == sources.SOURCES[0]["name"]
    assert rows[1][1] == sources.SOURCES[0]["url"]
    assert not rows[1][2].startswith("'")
    assert rows[1][3] == "沒有更新"
