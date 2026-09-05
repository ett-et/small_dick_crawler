# Spec — IEC 版本檢查

> **現況真相（living）。維護者 = worker（ship-time 自動）；Human 不手動維護。**
> Last-updated-by: #4（回補 2026-09-04；feature 本身 ship 於 #1 2026-09-04）
>
> **本檔答「這功能現在真的怎麼運作」。** 三個不重抄的鄰居：
> 需求 SSOT = [issue #1](https://github.com/ett-et/small_dick_crawler/issues/1)；
> 規則本體（該怎樣）= [`../ssot/business_logic.md`](../ssot/business_logic.md) + [`../ssot/api_contract.md`](../ssot/api_contract.md)（索引見 [`../ssot/README.md`](../ssot/README.md)）；
> 設計沿革 = `archived/2026/Q3/1-iec-publication-version-checker/plan_README.md` D1–D9。
> **本檔與 SSOT 不一致時以 SSOT 為準**（code 是 drift，per `repo_ssot_layout.md §7`）；
> 本檔與 code 不一致時以 code 為準（本檔是投影、修本檔）。

## Purpose

讓人按一下就知道 IEC publication 85813（IEC 62368-1 RLV）有沒有改版 —— 把「定期人工開網頁比對」變成「按按鈕看結果」，並在有變動時指出**哪一欄從什麼變成什麼**。

## Behavior（現況）

### 兩個動作

- WHEN 使用者 `POST /api/baseline` THEN the system SHALL 抓一次目標頁、把正規化後的現況寫成新基準，回 `status: "baseline_set"`（`app/main.py:66-69`、`:129-158`）
- WHEN 使用者 `POST /api/check` THEN the system SHALL 抓一次目標頁、與基準逐欄比對，回 `status: "updated"` 或 `"no_update"`，且 SHALL NOT 寫入基準（`app/main.py:71-74`、`:161-203`）
  - 現況佐證：全檔唯一的 `store.write_baseline` 呼叫在 `app/main.py:140`（`_run_set_baseline` 內）；`_run_check` 只寫 `last_check.json`（`app/main.py:195-202`）
- the system SHALL 在偵測到差異後持續回報 `updated`，直到有人執行 `POST /api/baseline` 為止（更新訊號 ⛔ 不自動清除）

### 基準不存在時

- WHEN `baseline.json` 不存在且使用者 `POST /api/check` THEN the system SHALL 回 `status: "no_baseline"`、SHALL NOT 判為有更新（`app/main.py:166-173`）
- the UI SHALL 在無基準時把「檢查版本」按鈕設為 disabled（`app/templates/index.html:110`）

### 失敗處理

- WHEN 目標頁連線失敗或非 HTTP 200 THEN the system SHALL 回 `status: "error"`、訊息前綴「抓取失敗」，且既有基準 SHALL 不變（`app/iec.py:35-48`、`app/main.py:109-115`、`:132-134`）
- WHEN HTML 內找不到或解析不出 `lifecycles` THEN the system SHALL 回 `status: "error"`、訊息前綴「解析失敗」—— ⛔ SHALL NOT 靜默回報成「沒有更新」（`app/iec.py:89-97`、`app/main.py:116-122`）
- WHEN HTML 內缺 `underDevelopmentProduct` 或其為空物件 THEN the system SHALL 正常回應、`under_development` 為 `null`（合法 = 目前沒有開發中版本）（`app/iec.py:99-108`）
- WHEN 基準檔存在但內容毀損 THEN the system SHALL 視同「沒有基準」（`app/store.py:29-38` 吞 `JSONDecodeError` / `OSError` 回 `None`）

### 比對範圍

- the system SHALL 只比對 `current_reference` / `current_edition` / `current_publication_date` / `lifecycle_entries` / `under_development` 五欄（`app/iec.py:170-176`）
- `checked_at` SHALL NOT 參與比對（比了會永遠回報有更新；`app/iec.py:169` 註解 + `tests/test_iec.py::test_checked_at_not_compared`）

### 節流

- WHEN 同一個動作在 `SMALLDICK_THROTTLE_SECONDS`（預設 10）秒內被重複觸發 THEN the system SHALL 回上次結果、帶 `throttled: true` + `throttle_wait_seconds`，且 SHALL NOT 對 IEC 發新請求（`app/main.py:23`、`:79-101`）
- the system SHALL 只快取「真的發出過對外請求」的結果 —— `no_baseline` ⛔ 不進快取（`app/main.py:99` 的 `_fetched` 旗標 + `:172`）
- 兩個動作 SHALL 各自計時、各自一把鎖 —— 其中一個動作進行中 SHALL NOT 阻擋另一個（`app/main.py:34-41`）

### 回應狀態值域

`baseline_set` / `no_baseline` / `no_update` / `updated` / `error` **五值**。前端對照表在 `app/templates/index.html:189-195`；未知值走 fallback（顯示原字串、經 `esc()`）。

### 呈現

- WHEN 回應含 `changes` THEN the UI SHALL 把 `under_development` / `lifecycle_entries` 攤成子項目逐列顯示（例：`開發中版本｜階段  CD → PCC`），⛔ SHALL NOT 直接印整包 JSON（`app/templates/index.html:158-186`）
- 動作完成後 the UI SHALL 重新抓 `GET /` 並換掉上方基準面板 / 上次檢查 / 兩顆按鈕的文案與 disabled 狀態（`app/templates/index.html:260-270`）

## Surface（現況 cite）

| 面 | 現況 |
|---|---|
| routes | `GET /`（`app/main.py:56`）、`POST /api/baseline`（`:66`）、`POST /api/check`（`:71`）、`GET /healthz`（`:52`）|
| models | **⛔ 無 DB / 無 ORM / 無 migration**。持久化 = 兩個 JSON 檔，見 `../data_model_map.md` |
| 持久化落點 | `<SMALLDICK_DATA_DIR>/baseline.json` + `last_check.json`，預設 `/data`（`app/store.py:20-22`）；atomic write = mkstemp → fsync → `os.replace`（`app/store.py:41-61`）|
| 解析管線 | `fetch_html`（`app/iec.py:35`）→ `extract_blocks` brace-matching（`:84`）→ `normalize`（`:123`）→ `diff`（`:187`）|
| 前端 | 單一 `app/templates/index.html`，零框架、零 CDN、零建置步驟 |
| 目標 | `DEFAULT_URL` 寫死 `https://webstore.iec.ch/en/publication/85813`（`app/iec.py:22`）；v1 不支援多目標 |
| 存取邊界 | ⛔ 無登入 / 無帳號 / 無角色 / 無使用者資料。基準是**全站共用的單一份**，任何訪客都能覆寫 |
| 關鍵 rule 出處 | 「檢查不得寫基準」「解析失敗不得當成沒更新」等**規則本體**在 [`../ssot/business_logic.md`](../ssot/business_logic.md) `§2` / `§4`；endpoint 語意與 `status` 值域在 [`../ssot/api_contract.md`](../ssot/api_contract.md) `§1`–`§2`。本檔只投影其現況實作 |

## Change log

- 2026-09-04 #1: 建立本 feature —— 抓取 / 解析 / 比對 / 單頁呈現；兩顆按鈕（檢查只讀、更新基準才寫）；per-action 節流；上線 `https://smalldick.etbiss.com`
- 2026-09-04 #4: **回補本 spec**（grandfather 補寫現況投影，per `living_spec_maintenance.md §6`）—— ⛔ 零行為變更
