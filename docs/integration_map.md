# small_dick_crawler Integration Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。「對目標站點該怎麼發請求」的**規則本體**在 [`ssot/business_logic.md`](ssot/business_logic.md) `§5`（外部禮節）—— 本檔 ⛔ 不重述規則，只記現在怎麼串。

## 外部整合清單

**只有一個。** 無第三方 API、無 SDK、無 webhook、無外寄郵件 / 通知、無 secret / 金鑰（`requirements.txt` 全部相依 = Flask + gunicorn + requests）。

| 對象 | 方向 | 協定 | 出處 |
|---|---|---|---|
| IEC webstore publication 85813 | **只出不進**（本服務單向 GET，⛔ 對方不會回呼本站）| HTTPS GET，單次、無 session、無 cookie | `app/iec.py:22`、`:35-48` |

## 請求現況

| 項目 | 值 | 出處 |
|---|---|---|
| URL | `https://webstore.iec.ch/en/publication/85813`（**寫死**）| `app/iec.py:22` |
| timeout | `30` 秒 | `app/iec.py:24` |
| User-Agent | `smalldick-iec-version-checker/1.0 (+https://smalldick.etbiss.com)`（標示身分）| `app/iec.py:23` |
| Accept | `text/html` | `app/iec.py:41` |
| 重試 | **⛔ 無**（失敗即回報，不自動 retry）| `app/iec.py:38-48` |
| 節流 | 同一動作 10 秒內不重發（`SMALLDICK_THROTTLE_SECONDS`）| `app/main.py:23`、`:79-101` |
| 觸發 | **僅使用者按按鈕**；⛔ 無排程、無預熱、無背景輪詢 | `app/main.py:66-74` |

## 資料契約（⚠️ 最脆弱的一點）

本服務**不呼叫 API，而是解析對方頁面內嵌的 JS 物件字面量** —— 沒有版本號、沒有相容性承諾，對方改版即斷。

- 抓取目標 = HTML 內 Alpine.js `x-data` 工廠函式 return 字面量裡的 `lifecycles: {…}` 與 `underDevelopmentProduct: {…}`（`app/iec.py:1-12` 檔頭）。
- 解析法 = 從 `<key>: {` 起做**大括號配對**（含字串 / 跳脫狀態機），⛔ 不用 regex（JSON 有巢狀 `{}`）、⛔ 不用 HTML parser（資料不是 DOM 節點）（`app/iec.py:51-81`）。
- `html.unescape()` 後 `json.loads()`（`app/iec.py:93`、`:103`）。
- ⛔ **不可**改用 `<script type="application/ld+json">`：服務端 HTML 內**根本沒有**該元素，它是前端 JS 動態注入的（plan `## Context`；issue #1 body 的舊敘述已由 comment 更正）。

## 失敗分類與處理

| 情境 | 例外 | 對外表現 | 對狀態的影響 |
|---|---|---|---|
| 連線 / DNS / 逾時 | `iec.FetchError` | `status=error`，訊息「抓取失敗：…」 | ⛔ 不寫任何檔 |
| 非 HTTP 200 | `iec.FetchError`（`app/iec.py:46-47`）| 同上 | ⛔ 不寫任何檔 |
| 找不到 `lifecycles` | `iec.ParseError`（`app/iec.py:89-91`）| `status=error`，「解析失敗」+「目標頁面結構可能已改變」 | ⛔ 不寫任何檔 |
| `lifecycles` JSON 壞 / 為空 | `iec.ParseError`（`app/iec.py:92-97`）| 同上 | ⛔ 不寫任何檔 |
| 缺 `underDevelopmentProduct` 或為空物件 | **⛔ 不是失敗** | 正常回應、`under_development: null` | 正常寫入 |

⚠️ **失敗只回給按按鈕的那個人**，伺服器端 ⛔ 不留紀錄 —— 見 [`observability_map.md`](observability_map.md)。

## 內部整合

| 對象 | 關係 | 出處 |
|---|---|---|
| `etchai_nginx`（同一台 VPS 的共用反向代理）| 本容器被它反代；⛔ 不反向依賴 | 見 [`deployment_map.md`](deployment_map.md) |
| 其他 repo | **⛔ 無** —— 本 repo 不引用任何 infra repo 的 code，也不被任何 repo 引用 | `aiREAD.md §1` |

## 擴充時第一個要動的點

`app/iec.py:22` 的 `DEFAULT_URL` 是寫死的單一目標；`normalize()` 已預留 `source_url` 參數與欄位（`app/iec.py:123`、`:160`），但呼叫端從未傳（`app/main.py:124`）。多目標時這裡是起點。
⚠️ **「來源（target）作為一級概念」目前未定義** —— 見 [`ssot/business_logic.md`](ssot/business_logic.md) `§1` 的 TBD-1。
