# small_dick_crawler Feature Map

> **地圖 = 現況投影 / 索引，⛔ 不是 SSOT**（per `living_spec_maintenance.md §8 (B)`）。
> 投影自 **code** 的部分：不一致時以 code 為準、修地圖。
> 投影自 **業務 SSOT**（`docs/ssot/`，索引見 [`ssot/README.md`](ssot/README.md)）的部分：不一致時**以 SSOT 為準、code 是 drift**。
> 維護 = ship-time（`§5` 子步 1b'）、**advisory 不擋 ship**。

## 功能模組

| 功能 | 模組（路徑）| 狀態 | Spec | Issue |
|---|---|---|---|---|
| IEC publication 85813 版本檢查（抓取 / 解析 / 比對 / 單頁呈現）| `app/` | 上線 `https://smalldick.etbiss.com`（2026-09-04）| [`specs/iec_version_check.md`](specs/iec_version_check.md) | [#1](https://github.com/ett-et/small_dick_crawler/issues/1) |

**⛔ 目前就這一個功能模組。** `app/` 下 3 支 python + 1 個 template：

| 檔 | 職責 |
|---|---|
| `app/iec.py` | 對外抓取 + brace-matching 解析 + 正規化 + 逐欄比對 |
| `app/store.py` | `baseline.json` / `last_check.json` 的 atomic 讀寫 |
| `app/main.py` | 4 個 route + per-action 節流 |
| `app/templates/index.html` | 單頁前端（零框架、零 CDN）|

`tests/` / `deploy/` / `active/` / `archived/` / `reviews/` / `docs/` **不是功能模組**。

## 明確沒有的能力（v1 現況，⛔ 非待辦清單）

| 沒有 | 現況佐證 |
|---|---|
| 定時 / 自動檢查、通知 | 全 repo 無 scheduler / cron / signal / task；`requirements.txt` 只有 Flask + gunicorn + requests |
| 多目標（使用者自填網址）| `app/iec.py:22` 單一 `DEFAULT_URL` 寫死；前端無輸入欄位 |
| 登入 / 帳號 / 角色 / 權限 | 全 repo 無 auth code（issue #1 `## Permission` 明示 v1 無權限模型）|
| 歷史保存（多筆快照 / 趨勢）| `app/store.py:21-22` 只有兩個單筆檔，新的直接覆寫舊的 |

---

## 地圖層現況

本 repo 落檔 7 張地圖。**哪 13 個視角、哪些落檔 / 哪些 `N/A` 與逐條理由，canonical 在 [`../aiPJINDEX.md`](../aiPJINDEX.md) `## 地圖層`**（repo 索引的正規歸宿）—— 本檔 ⛔ 不重列。
