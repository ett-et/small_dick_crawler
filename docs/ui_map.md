# small_dick_crawler UI / Page Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。管「頁面**怎麼走** / 入口在哪 / 狀態怎麼呈現」；「這功能怎麼運作」見 [`specs/iec_version_check.md`](specs/iec_version_check.md)。
> ⚠️ **route 語意 / `status` 值域 / 前端渲染對照表的規則本體在 [`ssot/api_contract.md`](ssot/api_contract.md) `§1`–`§4`** —— 本檔 ⛔ 不重述契約，只記現在畫面長怎樣。
> 不一致時：投影 code 的部分以 code 為準（修本檔）；投影該 SSOT 的部分**以 SSOT 為準、code 是 drift**。

## Route

| method | path | 回什麼 | 出處 |
|---|---|---|---|
| GET | `/` | 唯一的頁面（server-rendered Jinja）| `app/main.py:56-64` → `app/templates/index.html` |
| POST | `/api/baseline` | JSON，`status: baseline_set` \| `error` | `app/main.py:66-69` |
| POST | `/api/check` | JSON，`status: no_baseline` \| `no_update` \| `updated` \| `error` | `app/main.py:71-74` |
| GET | `/healthz` | 純文字 `ok` / 200 | `app/main.py:52-54` |

**⛔ 沒有第二個頁面、沒有跳頁、沒有 redirect、沒有 404 自訂頁。** 兩個 POST 由頁內 `fetch()` 呼叫、⛔ 不由表單 submit（`app/templates/index.html:244`）。

## 唯一頁面的三個區塊

| 區塊 | 元素 id | 內容 | 出處 |
|---|---|---|---|
| ① 目前的基準 | `#baselinebox` + `#lastcheck` | 版次 / 標準編號 / 開發中 / 建立時間；下方一行「上次檢查」| `index.html:76-105` |
| ② 動作 | `#btn-check`、`#btn-baseline` | 兩顆按鈕 + 說明 + 可收合的「怎麼判斷有更新？」| `index.html:108-136` |
| ③ 結果 | `#result` | 判定 + 訊息 + 頁面現況 + 差異表 + 時間；**預設 `hidden`，按下才出現** | `index.html:139`、`:234-235` |

## 狀態 → 畫面

| `status` | 畫面（icon / 色）| 出處 |
|---|---|---|
| `updated` | 🔔 有更新（warn 黃）| `index.html:189-195` |
| `no_update` | ✅ 沒有更新（ok 綠）| 同上 |
| `baseline_set` | 📌 基準已設定（neutral）| 同上 |
| `no_baseline` | ℹ️ 還沒有基準（neutral）| 同上 |
| `error` | ⚠️ 檢查失敗（err 紅）| 同上 |
| 未知值 | 原字串照顯示（neutral），經 `esc()` 逃脫 | `index.html:195`、`:199` |

**額外附帶提示**：`throttled: true` → 結果下方加一行「節流中：N 秒內不重複向 IEC 發請求，以上為上次結果」（`index.html:202-204`）。

## 空 / 忙 / 停用狀態

| 情境 | 畫面 | 出處 |
|---|---|---|
| 沒有基準（空狀態）| ①「還沒有建立基準 —— 請先按下方的『建立基準』」；②「檢查版本」**disabled**；「建立基準」文案（有基準時變「更新基準」）| `index.html:95`、`:110-111` |
| 沒做過檢查 | ①下方「還沒有做過任何檢查。」| `index.html:102` |
| 請求進行中 | **兩顆按鈕都 disabled**，被按的那顆文案換成「檢查中…」/「抓取中…」| `index.html:238-243`、`:273-274` |
| 請求結束 | 文案還原、兩顆重新啟用，但「檢查版本」再依 `data-nobaseline` 決定是否維持 disabled | `index.html:254-257` |
| 本站 endpoint 連不到 | ③ 顯示 ⚠️「無法連線到本站的檢查服務：…」（前端自造的 `error`）| `index.html:251-253` |

⚠️ **「檢查版本」的啟用狀態由三處協同決定**：Jinja 初次算（`:110`）→ 開頁時寫進 `dataset.nobaseline`（`:272`）→ 每次動作後由 `refreshPanel()` 重抓 `GET /` 覆寫（`:266-267`）。動這顆按鈕時三處要一起看。

## 差異表的呈現

`under_development` / `lifecycle_entries` 這兩個結構化欄位在差異表中被 `explode()` 攤成子列（`開發中版本｜階段`、`版次歷史｜新增版次` …），⛔ 不 `JSON.stringify` 整包印出（`index.html:158-186`、`:219-228`）。

## 前端資產

⛔ 零外部資源：CSS 與 JS 全部 inline 在 `index.html`，無 CDN、無 build step、無 static 目錄（`app/` 下只有 `templates/`）。深色模式靠 `prefers-color-scheme`（`index.html:13-19`）。
