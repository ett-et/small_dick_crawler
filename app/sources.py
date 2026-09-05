"""檢查來源的**唯一一份**定義（名稱 + 連結）。

設計依據見 `active/3-export-check-result-excel/plan_README.md` I1（落地 issue #3 D5）。

為什麼需要這個模組
------------------
issue #3 D5 要求 CSV 的「目標名稱 / 目標連結」兩欄**用畫面上「目標：」那一行既有的值**。
但那個名稱原本**寫死在 `templates/index.html` 的字面量裡**、後端拿不到 —— 要匯出就得上提，
讓樣板與 CSV **共用同一份**。⛔ 兩處各寫一份 = 第二份真相。

邊界（⛔ 別把這裡養大）
----------------------
- 這是「來源作為一級概念」的**最小可行第一步**，只做**名稱 + 連結**兩個欄位。
  ⛔ 不在此展開多來源模型（來源清單管理 / 新增第二個目標 / 各來源的抓取設定）——
  那是 issue #3 `## 明確不做` 列的獨立需求，另開票。
- **網址 ⛔ 不在這裡重打一次字串** —— 它的既有唯一定義是 `iec.DEFAULT_URL`，這裡沿用。
  在此重打就又生出第二份真相（正是 D5 要消滅的東西）。
- 結構是「一個 list、一列一筆」而不是兩個純字串常數：issue #3 `## Business Rules` 要求
  「欄位結構直接照多來源設計，未來加來源不需重做」→ 未來加來源時只改**資料**、不改結構。
"""

from __future__ import annotations

from . import iec

# 名稱字串原封取自 `templates/index.html` 的 `<p class="target">` 那一行（⛔ 一字未改）。
SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "IEC 62368-1:2023 RLV（publication 85813）",
        "url": iec.DEFAULT_URL,
    },
)
