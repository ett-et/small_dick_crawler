---
version: 2026-09-04
name: Business Logic SSOT — 版本檢查的判定與基準規則
scope: 「有沒有更新」怎麼判、基準（baseline）誰能寫、失敗怎麼算、對目標站點怎麼發請求
override: local-extends-not-overrides
change_gate: human-review-§2.6（repo 級：改本檔走 feat→dev PR + review gate；改到規則本體時需求面先動 issue）
domain_load_trigger: 動判定邏輯 / 基準寫入 / 節流 / 失敗處理 / 新增檢查來源之前
---

# Business Logic SSOT — small_dick_crawler

> **這是規則本體（該怎樣），⛔ 不是現況投影（現在長怎樣）。**
> code 與本檔不一致時，**以本檔為準、code 是 drift**（per `~/projects/project_maker/standards/repo_ssot_layout.md §7`）。
> ⛔ 本檔不列舉現況（現在的 edition 值 / 有哪些檔案 / 有哪些 endpoint）—— 那是地圖層的事。
>
> **本檔不重抄母框架**，只 pointer：落點與檔形契約見 `repo_ssot_layout.md §5`–`§7`。

## 0. 怎麼讀這張表

每條規則後面的 **來源** 標記其可追溯性，三種：

| 標記 | 意思 |
|---|---|
| `issue #1` | 需求 SSOT 已明文要求（`## Business Rules` / `## Edge Cases` / `## Acceptance` / `## Non-functional`）|
| `plan D<n>` | 設計時拍板，沿革見 `archived/2026/Q3/1-iec-publication-version-checker/plan_README.md` |
| `code-only` | ⚠️ **只在 code 裡成立、從未被獨立拍板**；本檔是它第一次被明文化。要推翻它成本低，但推翻前請先看括號裡的理由 |

行號 cite 的是**寫本檔當下**的位置（2026-09-04）；code 會動，函式 / 常數名才是穩定的錨。

---

## 1. 檢查對象（來源 / target）

- **R-T1｜v1 只追一個目標**：檢查對象是 IEC publication 85813 頁面，網址**寫死在 code**（`app/iec.py:22` `DEFAULT_URL`），⛔ 不提供使用者自行輸入網址。〔來源：issue #1 `## Business Rules`〕
- **R-T2｜快照必須帶來源網址**：每份 snapshot MUST 含 `source_url`，即使 v1 只有一個目標 —— 目的是讓未來擴充多來源時不必重新設計資料形狀（`app/iec.py:160`）。〔來源：issue #1 `## Data Model`〕

### ⚠️ TBD-1｜「來源（target）」作為一級概念**尚未定義**

系統目前**沒有「來源」這個實體** —— 只有一個寫死的網址常數，**沒有人類可讀的名稱**、沒有來源清單、沒有可設定性。

- `#3`（匯出 Excel）需要「目標名稱 / 目標連結」兩欄，其中「目標名稱」在系統裡不存在 → 見 `ett-et/small_dick_crawler#3` `## Data Model` 與 `## Open Questions` #5。
- 完整定義（多來源、來源清單管理）屬**多來源那張票**（`#3` `## 明確不做` 已明列其為 out of scope；該票**尚未開**）。

⛔ **本檔不自行拍板**（per `behavioral_constraints.md §2.8` 無 SSOT 不臆造）。拍板後回填本節。

---

## 2. 基準（baseline）的寫入權 —— 本 repo 最核心的一組規則

- **R-B1｜寫基準的入口只有一個**：只有「建立／更新基準」這個動作會寫基準。〔issue #1 `## Business Rules`；`app/main.py:129` `_run_set_baseline`〕
- **R-B2｜「檢查版本」⛔ 任何情況都不寫基準**，包含「偵測到有更新」的情況。〔issue #1；plan D8；`app/main.py:162,194`〕
- **R-B3｜更新訊號 ⛔ 不得被自動清除**：偵測到「有更新」之後，後續的「檢查版本」SHALL 持續回報「有更新」，直到**人明示**按下「建立／更新基準」（＝「我知道了」）為止。
  **為什麼是紅線**：若檢查順手覆寫基準，第二次按就會變成「沒有更新」—— **工具自己把警訊抹掉**。〔issue #1 `## Acceptance`；plan D8；回歸測試 `tests/test_api.py:88` `test_check_never_overwrites_baseline`〕
- **R-B4｜任一動作失敗（抓取失敗 / 解析失敗）→ ⛔ 不覆寫既有基準。**〔issue #1 `## Business Rules`；`app/main.py:130,132-134`〕
- **R-B5｜基準是全站共用的單一份**：無登入、無帳號 → **任何訪客都能覆寫它**。v1 明示接受此行為（工具僅供內部使用）。〔issue #1 `## Permission`〕
  ⚠️ 這是本 repo 唯一具「存取控制形狀」的規則 —— 為什麼沒有獨立的 `access_control.md`，見 `docs/ssot/README.md` 的 domain 判定表。
- **R-B6｜基準必須在容器重建後存活**：故基準檔落點 MUST 是掛載進來的持久化路徑，⛔ 不得是容器內的暫時路徑。〔issue #1 `## Edge Cases`；plan D3〕
- **R-B7｜寫入必須是原子操作**：同時多人按按鈕不得寫壞基準檔（同目錄暫存檔 → fsync → `os.replace` 換名；`app/store.py:41-61`）。〔issue #1 `## Edge Cases`〕

---

## 3. 「有更新」怎麼判

- **R-C1｜判定 = 整體逐欄比對**：把本次抓到的資料正規化成 snapshot，與基準**逐欄比對**，任一欄不同即「有更新」。〔plan D4；`app/iec.py:187` `diff`〕
- **R-C2｜參與比對的欄位是固定的一組**（`app/iec.py:170-176` `COMPARED_FIELDS`）：目前標準編號 / 目前版次 / 目前發布日 / 版次歷史 / 開發中版本。
  **⛔ 檢查時間（`checked_at`）不參與比對** —— 它每次都不同，比了就永遠說「有更新」。〔plan D4；`app/iec.py:169`〕
- **R-C3｜三種訊號由同一次整體比對涵蓋**，⛔ 不為 A/B/C 各寫一段判斷：
  A 目前版次變動 ／ B 出現更新的版次 ／ C 開發中版本狀態變動。〔issue #1 `## Business Rules`；plan D4〕
- **R-C4｜「開發中版本」從『有』變成『沒有』＝ 有更新**（代表該修訂案已發布或被撤銷）。〔issue #1 `## Edge Cases`〕
- **R-C5｜還沒有基準時按「檢查版本」→ 回報「還沒有基準」，⛔ 不得判為「有更新」**，且該按鈕在畫面上同時為停用狀態。〔issue #1 `## Business Rules`；`app/main.py:166-173`〕
- **R-C6｜正規化必須穩定**：欄位固定、list 排序固定 —— 同一份頁面永遠產出同一個結構，⛔ 不得因 dict / list 順序抖動而誤報「有更新」。〔plan D4；`app/iec.py:123-128,143`〕

---

## 4. 失敗怎麼算（本 repo 的第一紅線）

- **R-F1｜解析不到版本資料 = 失敗，⛔ 不得靜默當成「沒有更新」。**
  具體：頁內版本資料區塊缺席 / 解析失敗 / 解析出來是空的 → 一律判失敗，並明確回報「頁面結構可能已改變」。〔issue #1 `## Validation` + `## Edge Cases`；`app/iec.py:10-11,89-97`〕
- **R-F2｜「開發中版本」缺席（或為空物件）是合法的**，代表「目前沒有開發中版本」，⛔ 不得因此判失敗。〔issue #1 `## Validation`；`app/iec.py:99-108`〕
- **R-F3｜HTTP 非 200、連線錯誤、逾時 → 判失敗。**〔issue #1 `## Validation`；`app/iec.py:43-48`〕
- **R-F4｜失敗時 ⛔ 不覆寫基準**（＝ R-B4，此處重申因為它是失敗路徑最容易被寫壞的一條）。回歸測試：`tests/test_api.py:136` / `:152`。

---

## 5. 對目標站點的行為（外部禮節）

- **R-E1｜on-demand only**：⛔ 系統 SHALL NOT 在使用者未按按鈕的情況下對目標站點發出任何請求（無定時檢查、無背景輪詢、無預抓）。〔issue #1 `## Acceptance` + `## Business Rules`〕
- **R-E2｜一次使用者動作最多產生一次對外請求。**〔issue #1 `## Non-functional`〕
- **R-E3｜節流**：同一個動作在最小間隔內（`SMALLDICK_THROTTLE_SECONDS`，預設 10 秒；`app/main.py:23`）重複觸發 → ⛔ 不對外發新請求，直接回上次結果。〔issue #1 `## Edge Cases`；plan D5〕
- **R-E4｜節流是 per-action**：兩個動作各自計時、各自一把鎖，⛔ 不得互相阻擋（按了「檢查」不該把「更新基準」也鎖住；`app/main.py:34-41,79-101`）。〔plan D8〕
- **R-E5｜⛔ 只快取「真的發出過對外請求」的結果**。沒發出外部請求的結果（例如「還沒有基準」）快取了會說謊 —— 它會因為使用者按了另一顆按鈕而改變，卻沒有任何對外請求需要被節流。〔plan D8（本機實測踩到）；`app/main.py:99`；回歸測試 `tests/test_api.py:241`〕
- **R-E6｜請求 MUST 設逾時上限、MUST 帶可辨識身分的 User-Agent。**〔issue #1 `## Non-functional`；`app/iec.py:23-24`〕
- **R-E7｜節流不是一種「結果」**：節流只影響「有沒有真的去抓」，⛔ 不新增結果狀態。契約面怎麼表達見 `docs/ssot/api_contract.md` R-A2 / R-A3。〔plan D5〕
- **R-E8｜為保護 R-E1/R-E3 而存在的實作約束：⛔ 不得把 gunicorn 改成多 worker。**
  節流狀態存在程序記憶體內 → 多 worker 會各自為政，對目標站點的請求量變成 N 倍。〔plan D5；`Dockerfile:19-22`〕

---

## 6. 保存什麼、不保存什麼

- **R-D1｜只保存解析後的版本欄位，⛔ 不落地保存抓回來的原始 HTML。**〔issue #1 `## Non-functional`〕
- **R-D2｜「檢查版本」只寫「上次檢查」紀錄（時間 + 結果），⛔ 不寫基準**（＝ R-B2 的資料面；`app/main.py:194-202`）。〔plan D8〕
- **R-D3｜基準檔 ⛔ 不得含任何憑證 / 機敏資料。**〔issue #1 `## Non-functional`〕

### ⚠️ TBD-2｜「上次檢查」紀錄要存到什麼程度，尚未定義

現在存的欄位**不足以事後重建 `#3` 要的匯出表**（缺目標名稱、缺最新版次）。要擴充它、還是改由前端把結果送回後端產檔，是 `#3` 的未決題 —— 見 `ett-et/small_dick_crawler#3` `## Open Questions` #2。⛔ 本檔不自行拍板。

---

## 7. 不在本檔的東西（去哪找）

| 想找 | 去哪 |
|---|---|
| 前後端交換的格式契約（狀態值域 / 回應欄位 / endpoint 語意）| `docs/ssot/api_contract.md` |
| **現在長什麼樣**（實際行為投影、現值、有哪些檔）| 地圖層 / living spec，見 `docs/specs/` |
| **需求**（為什麼要做、驗收條件、UAT）| GitHub issue（`#1` = v1 需求 SSOT）|
| 設計決策的沿革與被推翻的替代方案 | `archived/2026/Q3/1-iec-publication-version-checker/plan_README.md` `## Decisions` |
| 母框架規則（落點 / 檔形 / 工作流）| `~/projects/project_maker/standards/*`（本 repo 只 pointer、⛔ 不重抄）|

## 變更記錄

- 2026-09-04：建檔（issue #4）。內容全部來自 issue #1 與 archived plan D1–D9 的既有規則 —— **本檔無 `code-only` 條目**（每條都追得到需求或設計拍板）。TBD-1 / TBD-2 指向 `#3` 與未來的多來源票。
