---
version: 2026-09-04
name: API Contract SSOT — 頁面與後端交換資料的契約
scope: 兩個動作 endpoint 的語意分工、結果狀態值域、回應欄位、健康檢查與前端交換面的約束
override: local-extends-not-overrides
change_gate: human-review-§2.6（repo 級：改本檔走 feat→dev PR + review gate；⛔ 不得只改 code 不改本檔）
domain_load_trigger: 動 endpoint / 回應欄位 / status 值域 / 前端渲染對照表之前
---

# API Contract SSOT — small_dick_crawler

> **這是契約本體（該長怎樣），⛔ 不是現況清單。**
> code（`app/main.py` 的 route + `app/templates/index.html` 的 `render()`）是**實作**；兩者不一致時**以本檔為準、code 是 drift**（per `~/projects/project_maker/standards/repo_ssot_layout.md §7`）。
> ⛔ 本檔不回答「現在總共有哪些 endpoint」（那是地圖層 `docs/specs/` 的事）；下列每一條都是**約束**。
>
> 前後端住在同一個 repo、同一個容器內（伺服器端渲染 + 同源 `fetch`），**沒有第三方 consumer** —— 所以本契約的成本很低、但一旦改了，兩端必須同一個 PR 內一起改。
>
> 來源標記同 `business_logic.md §0`：`issue #1` / `plan D<n>` / `code-only`（⚠️ 只在 code 裡成立、從未獨立拍板，本檔是它第一次被明文化）。

---

## 1. 動作語意綁在 endpoint 上

- **R-A1｜寫 / 讀分離是契約的一部分，⛔ 不只是 UI 拆分**：
  - `POST /api/baseline` ＝ **唯一**會寫基準的入口。
  - `POST /api/check` ＝ **只讀**，⛔ 任何情況都不得寫基準。
  - ⛔ 不得新增第二條會寫基準的路徑，⛔ 不得讓 `GET` 造成任何寫入。
  規則本體見 `docs/ssot/business_logic.md` R-B1 / R-B2。〔issue #1 `## Business Rules`；plan D8〕
- **R-A2｜結果狀態（`status`）的值域是封閉的五值**：
  `baseline_set` ／ `no_baseline` ／ `no_update` ／ `updated` ／ `error`。
  - ⛔ 不得回傳未列舉的 `status` 字串（前端靠這組值決定圖示與措辭；`app/templates/index.html:189-195`）。
  - 要新增第六種結果 → **先改本檔 + 改前端對照表 + 改 issue 的驗收敘述**，⛔ 不得靠 code 悄悄長出新值。
  〔issue #1 `## Acceptance`（v2 由四值擴為五值）；plan D5 / D8；回歸測試 `tests/test_api.py:184`〕
- **R-A3｜節流用旗標表達、⛔ 不佔 `status` 值域**：回應 MUST 帶 `throttled`（布林）；`throttled: true` 時 MUST 另帶 `throttle_wait_seconds`（數值、秒）。此時 `status` ＝ **上一次真的抓過的那次結果**。〔plan D5；`app/main.py:93-96`〕

## 2. 回應形狀

- **R-A4｜兩個動作一律 `HTTP 200` + JSON body；業務失敗以 `status: "error"` + `message` 表達，⛔ 不用 4xx/5xx 表達業務結果。**
  **代價明示（呼叫端必須知道）**：⛔ 不可用 HTTP 狀態碼判斷成功與否，**必須看 `status`**。
  〔`code-only` —— `app/main.py:96,101` 恆回 200；此契約從未被獨立拍板，但前端已依賴它（`index.html:244-246` 只讀 body、不看狀態碼）。要改成語意化狀態碼 → 前端要一起改〕
- **R-A5｜必有欄位**：`status`、`message`（人可讀、zh-TW）、`checked_at`。〔issue #1 `## Acceptance`；`app/main.py:110-122,142-158,180-192`〕
- **R-A6｜有抓到資料時 MUST 帶 `snapshot`；有比對過時 MUST 帶 `changes`（list）**。
  `changes` 的每一筆 MUST 含 `field` / `label` / `before` / `after` 四欄 —— 少了 `field`，前端就無法把結構化欄位攤成子項目（per plan D9「差異表逐項攤開、⛔ 不直接印 JSON」；`app/iec.py:197-204`、`app/templates/index.html:158-186`）。〔issue #1 `## Acceptance`；plan D9〕
- **R-A7｜⛔ 內部旗標不得外洩到回應**：用來控制節流的內部欄位（`_fetched`）MUST 在回應前移除。〔`code-only` —— `app/main.py:99`；已有回歸測試守住 `tests/test_api.py:255`〕

## 3. 健康檢查

- **R-A8｜`GET /healthz` 是純存活探針**：回 `200`，⛔ 不得依賴任何對外請求、⛔ 不得依賴狀態檔是否存在。
  **理由**：健康檢查若依賴 IEC，IEC 一掛就會被部署層誤判成「本服務死了」。〔`code-only` —— `app/main.py:52-54` 無條件回 `ok`；部署驗收確實拿它當存活判準（`aiREAD.md §7`）〕

## 4. 前端交換面的約束

- **R-A9｜⛔ 零外部 CDN、零前端框架**：頁面 SHALL NOT 引用任何外部資源。〔issue #1 `## Technical Constraints`；有 `[auto]` 驗收在守（archived plan `## Acceptance`）〕
- **R-A10｜⛔ 前端不得自存一份基準狀態**：動作完成後要更新畫面上方面板，一律**重新向伺服器要**，維持單一真相來源。〔`code-only` —— `app/templates/index.html:247-250,260-270`；這條是「⛔ 不製造第二份真相」在前端的落地〕
- **R-A11｜瀏覽器 ⛔ 不得直接連目標站點**：抓取一律在伺服器端執行（跨來源限制 + 節流只能在伺服器端執行）。〔issue #1 `## Technical Constraints` + `## Business Flow`〕

---

## ⚠️ TBD-3｜匯出下載的契約未定

`#3`（檢查結果匯出 Excel）會新增一個下載動作，但它的契約有四題**尚未拍板**：資料從哪來（後端存全 vs 前端回送）、真 `.xlsx` vs CSV、失敗列怎麼填、按鈕亮起的條件。
→ 見 `ett-et/small_dick_crawler#3` `## Open Questions` #1–#4。⛔ 本檔不自行拍板；拍板後於此新增 `R-A12+`。

已可先確定、且**不因上述四題而變**的一條：**下載動作 SHALL NOT 對目標站點發出任何請求**（否則變相繞過節流）—— 但它要等該票落地才進本檔。〔來源：`#3` `## Non-functional`〕

## 變更記錄

- 2026-09-04：建檔（issue #4）。R-A1/A2/A3/A5/A6/A9/A11 來自 issue #1 與 archived plan D5/D8/D9；**R-A4 / R-A7 / R-A8 / R-A10 標 `code-only`** —— 只在 code 裡成立、本檔是首次明文化，⛔ 未經獨立拍板。TBD-3 指向 `#3`。
