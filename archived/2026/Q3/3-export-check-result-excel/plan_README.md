---
slug: export-check-result-excel
title: 檢查結果匯出 CSV — 檢查後「下載結果」按鈕亮起，一列一個來源
created: 2026-09-05
type: LocalPlan
upstream: issue #3
branch: feat/3-export-check-result-excel
shipped: true
dev_merged: true
---

# 檢查結果匯出 CSV

## Tracking

Issue: https://github.com/ett-et/small_dick_crawler/issues/3

## Goal

在既有單頁工具上加第三顆按鈕「下載結果」：跑完「檢查版本」後由停用變成可按，按下去下載一份
**帶 UTF-8 BOM 的 CSV**，一列一個檢查來源、四欄固定（目標名稱 / 目標連結 / 最新版次 / 版次查詢結果）。

需求 SSOT = issue #3（本 plan ⛔ 不重抄需求、只定**怎麼做**）。

## Context

**既有實作現況**（本 plan 要接進去的地方）：

| 事實 | 位置 | 對本 plan 的影響 |
|---|---|---|
| 目標名稱 `IEC 62368-1:2023 RLV（publication 85813）` **寫死在樣板字面量** | `app/templates/index.html:72` | D5 要求樣板與 CSV 共用同一份 → **必須上提**（見 I1）|
| 目標網址的唯一定義是 `iec.DEFAULT_URL`，樣板由 `index()` 以 `source_url=` 傳入 | `app/iec.py:22` / `app/main.py:61` | URL 已經是單一定義 → 上提時**沿用**、⛔ 不另造第二份 |
| 節流狀態 `_throttle` 已經是 **程序內記憶體 dict**、per-action | `app/main.py:34-36` | D2「後端記憶體、不落檔」有現成先例，不是新機制 |
| 節流會**重放上一次的結果**（`throttled: true`）| `app/main.py:88-96` | 匯出狀態的旗標 ⛔ 不能被快取進 `_throttle`，否則會說謊（見 I3）|
| gunicorn 固定 `--workers 1` | `Dockerfile:20-22` | D2 記憶體狀態的**前提**；本 plan 讓這條紅線又多綁一個東西 |
| 前端 `refreshPanel()` 在每次成功動作後**再打一次 `GET /`**（帶 `X-Panel: 1` header）| `app/templates/index.html:260-270` | ⚠️ **陷阱**：若 `GET /` 無條件清除匯出，檢查完立刻就被自己的面板刷新清掉、按鈕永遠不會亮（見 I2）|
| `_run_check` 有三條返回路徑：`no_baseline` / `error` / `updated\|no_update` | `app/main.py:161-203` | 逐條決定要不要點亮下載鈕（見 I4）|
| baseline / 檢查失敗共用 `_fetch_snapshot()` 的 error dict | `app/main.py:104-126` | 錯誤發生在**哪個動作**必須分開處理，否則「建立基準失敗」會誤點亮下載鈕（違反 D1）|

**既有測試基線**：33 條全綠（`env -u SMALLDICK_THROTTLE_SECONDS -u SMALLDICK_DATA_DIR ./.venv-test/bin/python -m pytest -q`，2026-09-05 實跑確認）。

**與 `docs/ssot/business_logic.md` TBD-1 的關係**：issue #3 D5 指出本工作是「來源作為一級概念」的最小可行第一步。
⛔ 本 plan **只做名稱 + 連結兩個欄位**，不展開多來源模型；且 `docs/ssot/` 目錄本身由 **issue #4**
（`feat/4-repo-ssot-and-map-scaffold`，PR 待審）建立 — 本 plan **⛔ 不碰該目錄**，避免兩條 branch 撞同一個檔。

## Decisions

> **需求級決策 D1–D5 的 SSOT = issue #3 `## Decisions`**（Human 2026-09-04 拍板）。
> 本段 ⛔ 不重抄、⛔ 不推翻，只在需要時 pointer 引用。
> 下列 **I1–I6 是實作級決策** —— issue 沒覆蓋到的分岔，與 D1–D5 正交。

### I1 — 來源定義上提到 `app/sources.py`（D5 的落地方式）

- 規則：新增 `app/sources.py`，內含**唯一一份**來源清單：

  ```python
  SOURCES = ({"name": "IEC 62368-1:2023 RLV（publication 85813）", "url": iec.DEFAULT_URL},)
  ```

  - 樣板：`index()` 改傳 `targets=sources.SOURCES`，`<p class="target">` 以 `{% for t in targets %}` 渲染 `t.name` / `t.url`。
  - CSV：`app/export.py` 讀同一個 `SOURCES`。
  - **名稱只有這一份定義；網址沿用既有的 `iec.DEFAULT_URL`**（⛔ 不在 `sources.py` 重打一次網址字串，那就變第二份真相了）。
- 理由：D5 明文「⛔ 不可在兩處各寫一份」。上提到後端模組是讓「樣板讀得到、CSV 也讀得到」的最小改動。
- 為什麼是 tuple of dict 而不是純字串常數：issue `## Business Rules`「欄位結構直接照多來源設計，未來加來源不需重做」。
  一個 list + 一列一筆的迴圈，加第二個來源時只改資料、不改結構。**⛔ 但本 plan 不新增第二個來源、不做來源管理**（issue `## 明確不做`）。
- 替代方案：
  - 名稱寫在樣板、CSV 再寫一份（**拒絕：D5 明文禁止**）
  - 把名稱塞進 `iec.py`（拒絕：`iec.py` 的職責是「怎麼抓怎麼解析」，「這個來源對人叫什麼」是展示層概念，混進去會讓未來多來源時難拆）
  - 直接建 `docs/ssot/sources.md` 定義（拒絕：跨 branch 撞 issue #4；且 D5 明文只做兩個欄位、不展開模型）

### I2 — 匯出狀態存 module-level 記憶體；`GET /` 清除，但 `X-Panel: 1` 豁免

- 規則：`app/main.py` 加 module-level `_export: dict | None`。
  - 「檢查版本」成功 / 失敗時**覆寫**它（單一份、新的蓋舊的）。
  - `GET /` **清成 `None`**（D2 丙：重整後按鈕變暗）。
  - **例外：帶 `X-Panel: 1` header 的 `GET /` 不清除。**
  - 下載動作 **⛔ 不清除**（D2：同一次頁面內可重複下載）。
  - ⛔ 完全不落檔（D2）—— 沒有任何 `store.write_*` 參與匯出路徑。
- **⚠️ 誠實界定（一）—— `GET /` 帶副作用**：HTTP 語意上 GET 應該是安全的（safe method、不改變伺服器狀態）。
  這條規則**明確違反**該語意。這是為了精確實現 D2「丙」付出的代價，**Human 已知悉並記在 issue #3 `## Decisions` D2 連帶影響**，
  ⛔ 不是疏忽。替代做法（前端產 session token、後端按 token 存）能保住 GET 純淨，但要多一套機制 —— 以本工具的規模不划算。
  **本條同時要求在 `app/main.py` 的 `index()` 內以註解明寫此取捨**（⛔ 不許實作得像沒這回事）。
- **⚠️ 誠實界定（二）—— `X-Panel` 豁免是必要條件，也是一個新的軟弱點**：
  既有前端在每次成功動作後會呼叫 `refreshPanel()` 再打一次 `GET /`。若不豁免，檢查完的下一個 request 就把匯出清掉、
  **D1「檢查後按鈕變亮」根本無法成立**。豁免的判準是**用戶端可控的 header** —— 理論上可被偽造。
  誠實界定其影響面：偽造的最壞結果 = 讓某人自己的匯出快照晚一點被清掉 / 早一點被清掉，
  **沒有資料外洩、沒有寫入、沒有對 IEC 發請求**（`_export` 內只有本來就顯示在同一個頁面上的資訊）。故接受。
  - 語意上也站得住：`X-Panel: 1` 的請求是「局部面板刷新」，**不是**「開頁 / 重整」—— D2 清除的觸發條件本來就是後者。
- 替代方案：
  - `GET /` 無條件清除（**拒絕：實際上會讓功能完全不動**，見上）
  - 改掉 `refreshPanel()` 不打 `GET /`（拒絕：那要改既有的面板刷新機制、動到 issue #1 已驗收的行為，範圍外）
  - session token（拒絕：見上，機制成本不划算；**若 UAT 認為 GET 副作用不可接受 → 走 C1 停手上浮**）

### I3 — 按鈕亮暗的真相在後端：回應帶 `export_ready`，⛔ 不進節流快取

- 規則：`POST /api/check` 與 `POST /api/baseline` 的 JSON 回應都帶布林 `export_ready`，
  **在 `_throttled()` 包裝層即時計算**（`_export is not None`）、⛔ 不寫進被快取的 result dict。
  前端 `btnDownload.disabled = !d.export_ready`。`GET /` 渲染時同樣由後端決定 `disabled` 屬性。
- 理由：
  - 若讓前端自己判斷「剛剛按的是檢查 → 亮」，D1 的規則就有第二份實作（前端一份、後端一份）→ 會漂移。
  - **⛔ 不能放進被快取的 result**：節流會重放 10 秒前的 result dict，裡面的 `export_ready` 是 10 秒前的事實；
    期間若有人重整過頁面，旗標就會說謊（按鈕亮著但下載回 409）。這是既有節流機制踩過同一類坑的重演
    （見 archived plan D8「⛔ 節流只快取真的抓過 IEC 的結果」）。
- 替代方案：前端依 status 自行推斷（拒絕：第二份真相）／每次都多打一支 `GET /api/export/status`（拒絕：多一趟往返、無收益）

### I4 — `no_baseline` **不**點亮下載鈕

- 規則：「檢查版本」在 `no_baseline` 分支 **不寫入 `_export`、也不清除既有的**；只有 `updated` / `no_update` / `error`
  三條路徑會覆寫 `_export`。「建立／更新基準」的**任何**路徑（含其失敗）⛔ 一律不碰 `_export`（D1）。
- 理由：issue #3 `## Business Rules` 原文是「**沒有可下載的結果時停用**」。`no_baseline` 代表根本沒發生比對、
  沒有任何檢查結果（也沒對 IEC 發過請求）→ 屬於「沒有可下載的結果」。
  D1 又明文把按鈕語意鎖成「匯出**檢查結果**」、⛔ 不擴成「匯出目前狀態」——「還沒有基準」是狀態、不是檢查結果。
- **⚠️ 誠實界定**：這條是 D1/D2 **沒有直接覆蓋的邊界**，由我依 `## Business Rules` 原文推導。
  若 Human 在 UAT 認為「按了檢查就該能下載，即使沒基準」→ 走 **C2** 停下改，⛔ 不自行擴大解釋。
- 替代方案：`no_baseline` 也產一列（拒絕：那一列的「最新版次」「版次查詢結果」都無真實內容，等於輸出噪音）

### I5 — CSV 產出獨立成 `app/export.py`（stdlib `csv` + `io`，⛔ 零新相依）

- 規則：
  - 欄位**固定四欄、固定順序**：`目標名稱` / `目標連結` / `最新版次` / `版次查詢結果`（issue `## UAT Checklist` 明列）。
  - 一列一個來源，逐一走訪 `sources.SOURCES`（v1 = 一列）。
  - 編碼 `utf-8-sig`（**= UTF-8 BOM，D4 硬要求**）；換行 `\r\n`（Excel / CSV 慣例）。
  - 逸出交給 `csv.writer` 處理（值裡有逗號 / 引號 / 換行時自動加引號）—— ⛔ 不手工拼字串。
  - **公式注入中和（self-review r1 finding #1 補）**：以 `= + - @ \t \r` 開頭的值加單引號前綴強制成文字。
    理由：「最新版次」欄的內容有一部分來自**外部抓回來的 IEC 頁面**，而本功能的重點就是「拿去 Excel 開」——
    等於把外部內容直接餵進 Excel 的公式引擎。實務上四個欄位都不會以那些字元開頭
    （`IEC …` / `https://…` / `Edition …` / `抓取失敗：…`）→ **正常情況下不改變任何輸出**，
    ⛔ 不影響 D5「與畫面顯示完全一致」。
  - 欄位語意：

    | 欄 | 成功時 | 失敗時（D3）|
    |---|---|---|
    | 目標名稱 | `sources.SOURCES[n]["name"]` | **同左**（D5：名稱不從抓取結果推導 → 失敗照樣有名字）|
    | 目標連結 | `sources.SOURCES[n]["url"]` | **同左** |
    | 最新版次 | `Edition 4.0（2023-05-26）・IEC 62368-1:2023`（與頁面「頁面現況」同構）| **失敗原因全文**（e.g. `抓取失敗：連線逾時`）⛔ 不留白 |
    | 版次查詢結果 | `有更新` / `沒有更新` | `檢查失敗` |
  - 檔名 `iec-check-YYYYMMDD-HHMMSS.csv`（**純 ASCII** —— 中文檔名要處理 `Content-Disposition` 的 RFC 5987 編碼，沒必要）。
- 理由：D4 明文「⛔ 不引入 `openpyxl`，零額外相依」。`csv` + `io` 是 stdlib。
  拆成獨立模組讓「怎麼組表」可以純函式離線測，不必經過 HTTP 層。
- **「失敗原因」的來源**：`_fetch_snapshot()` 已經產出人話訊息（`抓取失敗：…` / `解析失敗：…`），直接沿用 →
  ⛔ 不另造一套失敗文案（那會是第二份真相，且與頁面上顯示的不一致）。
- 替代方案：`openpyxl` 產 `.xlsx`（**拒絕：D4**）／手工字串拼接 CSV（拒絕：逸出一定寫錯）／中文檔名（拒絕：見上）

### I6 — endpoint `GET /api/export.csv`；沒有結果時回 **409**

- 規則：`GET /api/export.csv` 回 `text/csv; charset=utf-8` + `Content-Disposition: attachment`。
  `_export is None` 時回 **409 Conflict** + JSON `{"status": "no_export"}`。
  - **⛔ 本 endpoint 一律不呼叫 `iec.fetch_html()`** —— 它只讀 `_export`，連 `store` 都不碰（issue 紅線 + `## Acceptance` 有 `[auto]` 在驗）。
- 理由：狀態碼要能讓「按鈕亮著但實際沒東西」這種不一致**吵出來**而不是靜默回空檔。
  409（狀態衝突）比 404（資源不存在）更貼切 —— 這個 endpoint 一直存在，只是當下沒有可匯出的結果。
- 替代方案：404（拒絕：語意是「路徑不存在」）／回 200 + 空 CSV（**拒絕：靜默失敗**，違反 repo 一貫的「失敗要吵」紅線）

## Approach

1. **`app/sources.py`（新）** —— `SOURCES` tuple（per I1），名稱字串從 `index.html` 原封搬過來、⛔ 一字不改。
2. **`app/export.py`（新）** —— `HEADERS` 常數 + `rows_from_check(result, targets)` + `to_csv_bytes(rows)` + `filename_for(checked_at)`（per I5）。純函式、不碰 Flask、不碰網路。
3. **`app/main.py`（改）**
   - module-level `_export`；`_set_export()` / `_clear_export()` 兩個小 helper。
   - `index()`：先依 `X-Panel` 決定要不要清（per I2、**含取捨註解**）→ 再算 `export_ready` 傳進樣板；`source_url=` 改成 `targets=`。
   - `_run_check()`：`updated` / `no_update` / `error` 三路寫 `_export`；`no_baseline` 不碰（per I4）。
   - `_run_set_baseline()`：⛔ 完全不碰 `_export`（含其 error 路徑）。
   - `_throttled()`：回應統一補 `export_ready`（per I3、快取外）。
   - 新 route `GET /api/export.csv`（per I6）。
4. **`app/templates/index.html`（改）** —— `<p class="target">` 改讀 `targets`；`.btns` 加第三顆 `#btn-download`（`{% if not export_ready %}disabled{% endif %}`）；`run()` 的 finally 依 `exportReady` 還原下載鈕；下載以 `location.href` 觸發。說明文字補一句。⛔ 不引入任何 CDN / 框架。
5. **測試** —— `tests/test_export.py`（新，純函式層）+ `tests/test_api.py`（補 endpoint / 按鈕 / 生命週期 / 不打 IEC）。既有 33 條 ⛔ 一條都不許改語意。
6. **自審 sidecar** —— `reviews/self-review-3-r1.md`，有 finding 自己修並記錄處置。
7. **文件同步** —— 見 `## Doc Sync Scope`。
8. **收尾** —— commit（`Refs #3`）→ PR base `dev` → 翻 `needs-code-review`。⛔ 不 merge、⛔ 不關 issue。

### 需決定

（目前無；有新分岔時移入 `## Decisions`）

## Test Strategy

- Unit: yes — `app/export.py` 的組列 / 逸出 / BOM / 欄序、`app/sources.py` 的單一定義（`tests/test_export.py`）
- E2E: yes — Flask test client 打 `GET /` + `POST /api/check` + `POST /api/baseline` + `GET /api/export.csv`，外部抓取一律 stub（`tests/test_api.py`）
- UAT: yes — Human 照 issue #3 `## UAT Checklist` 於 dev port server 逐條跑，11 條
- 依據: standards/test_strategy_layering.md

## Checkpoints

| ID | Trigger | Stop condition | User decision needed |
|----|---------|----------------|---------------------|
| C1 | UAT 時 Human 認為 `GET /` 帶副作用（I2）不可接受 | 停手上浮，⛔ 不自行改用 session token 機制 | 是否值得為「保住 GET 純淨」多引入一套 session token 機制（D2 已知取捨的再議）|
| C2 | UAT 時 Human 認為 `no_baseline` 也該點亮下載鈕（I4 的邊界判定） | 停下改，⛔ 不自行擴大解釋 | `no_baseline` 到底算不算「檢查結果」 |
| C3 | 實作中發現 D1–D5 任兩條互相衝突、非推翻其一不可 | 停手上浮 | 需求 SSOT 只有 Human 能改（issue #3）|

## Acceptance

- [auto] the CSV SHALL 以 UTF-8 BOM（`\xef\xbb\xbf`）開頭 — `pytest tests/test_export.py::test_csv_starts_with_utf8_bom`
- [auto] the CSV SHALL 有且僅有四欄、順序為 `目標名稱,目標連結,最新版次,版次查詢結果` — `pytest tests/test_export.py::test_headers_are_four_columns_in_fixed_order`
- [auto] the CSV SHALL 一個來源產生一列 — `pytest tests/test_export.py::test_one_row_per_source`
- [auto] WHEN 欄位值內含逗號 / 引號 / 換行 THEN the CSV writer SHALL 正確逸出、SHALL NOT 讓欄位錯位 — `pytest tests/test_export.py::test_values_with_separators_are_quoted`
- [auto] WHEN 欄位值以 `= + - @` 開頭 THEN the CSV SHALL 中和成文字、SHALL NOT 讓 Excel 當公式執行；正常值 SHALL NOT 被改動 — `pytest tests/test_export.py::test_formula_injection_is_neutralized tests/test_export.py::test_normal_values_are_untouched`
- [auto] WHEN 檢查失敗 THEN the CSV SHALL 在「最新版次」欄寫入失敗原因、SHALL NOT 留白，且「目標名稱」與「目標連結」SHALL 仍有值 — `pytest tests/test_export.py::test_error_row_keeps_name_and_writes_reason`（D3 + D5）
- [auto] the target name SHALL 只有一份定義、頁面與 CSV SHALL 取自同一份 — `pytest tests/test_api.py::test_target_name_is_shared_between_page_and_csv`（D5）
- [auto] WHEN 尚未做過檢查 THEN `GET /` 渲染的下載按鈕 SHALL 為 disabled — `pytest tests/test_api.py::test_download_button_disabled_on_fresh_page`（D1）
- [auto] WHEN `POST /api/check` 成功 THEN 回應 SHALL 帶 `export_ready == true` 且 `GET /api/export.csv` SHALL 回 200 — `pytest tests/test_api.py::test_check_enables_download`（D1）
- [auto] WHEN `POST /api/baseline`（含其失敗路徑）THEN 回應 SHALL 帶 `export_ready == false` 且 `GET /api/export.csv` SHALL 回 409 — `pytest tests/test_api.py::test_baseline_never_enables_download`（D1）
- [auto] WHEN 檢查後發生 `GET /`（開頁 / 重整）THEN the system SHALL 清除匯出快照、下載按鈕 SHALL 變回 disabled — `pytest tests/test_api.py::test_index_clears_export`（D2）
- [auto] WHEN 檢查後的請求帶 `X-Panel: 1` THEN the system SHALL NOT 清除匯出快照 — `pytest tests/test_api.py::test_panel_refresh_does_not_clear_export`（D2 / I2）
- [auto] WHEN 同一次頁面內重複下載 THEN the system SHALL 每次都回相同內容的 200、SHALL NOT 因下載而清除 — `pytest tests/test_api.py::test_download_twice_in_same_page`（D2）
- [auto] WHEN 下載 CSV THEN the system SHALL NOT 對 IEC 發出任何請求 — `pytest tests/test_api.py::test_download_does_not_hit_iec`（issue 紅線）
- [auto] WHEN 檢查失敗（`no_baseline` 除外）THEN 下載按鈕 SHALL 仍亮起、CSV SHALL 輸出失敗列 — `pytest tests/test_api.py::test_failed_check_is_still_exportable`（D3）
- [auto] `POST /api/check` 的任何路徑 SHALL NOT 寫入基準檔 — `pytest tests/test_api.py::test_check_never_overwrites_baseline`（既有紅線回歸）
- [auto] the repo SHALL NOT 因本工作新增任何 runtime 相依 — `git diff origin/dev...HEAD -- requirements.txt | wc -l` 為 0（D4）
- [auto] the app SHALL NOT 引用任何外部 CDN 資源 — `grep -rE "https?://(cdn|unpkg|jsdelivr|fonts\.googleapis)" app/ | wc -l` 為 0（既有紅線回歸）
- [auto] 既有 33 條測試 SHALL 全數維持綠、且總數 SHALL 為 59 — `env -u SMALLDICK_THROTTLE_SECONDS -u SMALLDICK_DATA_DIR ./.venv-test/bin/python -m pytest -q`
- [manual] `app/main.py` 的 `index()` SHALL 以註解明寫「GET 帶副作用」的取捨 — 讀檔確認（I2 誠實界定要求）
- [uat] Human 照 issue #3 `## UAT Checklist` 11 條於 dev port server 逐條驗收（含用 Excel 開啟確認中文不亂碼）

## Doc Sync Scope

**Must update**：
- `aiPJINDEX.md` — 「功能模組」的模組內檔案表補 `app/sources.py` / `app/export.py`；`app/main.py` 一列補新 endpoint；「Plan 現況」`active/` 由 0 改 1
- `aiREAD.md` — §3 專案結構樹補兩個新檔；§6 開發 loop 的測試條數（33 → 新數字）

**Audit only**：
- `CLAUDE.md` — 技術棧段（Flask + gunicorn、零框架零 CDN）**預期不變**（D4 零新相依）；確認無需改
- `README.md` — 一句話定位不變

**Out of scope** / **Do not touch**：
- `docs/ssot/**` — 由 **issue #4**（`feat/4-repo-ssot-and-map-scaffold`，PR 待審）建立與擁有。⛔ 本 branch 不建、不改，避免兩條 branch 撞同一批檔
- `deploy/nginx/**`、`Dockerfile`、`docker-compose*.yml` — 本工作不改部署面（同一個容器、同一個 port、無新相依）
- `~/projects/project_maker/standards/**`、其他 repo — 不涉及

## 變更記錄

- 2026-09-05：建立 plan，寫入 I1–I6 實作級決策（需求級 D1–D5 的 SSOT 在 issue #3、本 plan 不重抄）。`## Context` 的既有實作事實均為本 session 讀檔實查；基線 33 條測試實跑確認全綠。（來源：issue #3 `## Decisions` + 本 session 讀 `app/` 全檔）
- 2026-09-05：實作完成。59 條測試全綠（基線 33 → +14 endpoint / +12 純函式）。
- 2026-09-05：**self-review r1 三條 finding 全修**（sidecar `reviews/self-review-3-r1.md`，verdict PASS / classification none）：
  (1) **中** — CSV 公式注入（匯出內容部分來自外部抓回的頁面、而本功能就是拿去 Excel 開）→ I5 補「公式注入中和」規則 + 2 條測試；
  (2) 低 — 我加的第三顆 disabled 按鈕**弱化了既有測試** `test_check_button_disabled_without_baseline`（原本只看整頁有無 `disabled` 字串）→ 收斂到 btn-check 自己的 tag，⛔ 語意未改、是把它改回真的在驗它名字說的事；
  (3) 低 — 「建立／更新基準」對**已存在**匯出快照的處置（不清除）無測試釘住 → 補 `test_baseline_does_not_clear_an_earned_export`。
  （來源：本 session inline 自審；⚠️ 非獨立 reviewer，界定見 sidecar 開頭）
- 2026-09-05：`## Acceptance` 隨上述補 1 條（公式注入中和）、測試總數條由「33 綠」改為「33 綠 + 總數 59」。
- 2026-09-05：**shipped** —— Human 於本機 `localhost:21003` 驗收 pass 並授權部署。（來源：Human 2026-09-05）
