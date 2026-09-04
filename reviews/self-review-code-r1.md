---
classification: env
verdict: REQUEST_CHANGES
round: 1
reviewer: inline（原本派的獨立 sub-reviewer 撞帳號用量上限中斷，見下方誠實界定）
date: 2026-09-04
target: git diff origin/dev...HEAD（全部實作）
---

# code self-review r1

## ⚠️ 誠實界定：本輪 reviewer 獨立性打折

原本派了**獨立 sub-reviewer**，但它在讀完 SSOT 後**撞上帳號用量上限中斷**
（`session limit · resets 7:40pm Asia/Taipei`）。

- 依 `behavioral_constraints.md §2.14 觸發前提` + `§2.21`：**外部資源中斷 ≠ 設計性收斂失敗**
  → **⛔ 不翻 `needs-code-review-check`**、**⛔ 不計入 3-strike**。
- 為不阻塞部署，本輪改由**同一個 session inline 自審**。
  **這比獨立 sub-reviewer 弱** —— 寫 code 的人審自己的 code，看不見自己的盲點。
- **補償**：本輪把每一項都做成**可執行的驗證**（實跑 parser 邊界案例、實測原子寫入失敗路徑、
  grep 逐行確認不變量、加併發回歸測試），而不是用讀的下結論。**證據附在下方各項。**
- 額度恢復後 SHOULD 補跑一輪真正獨立的 review。

## 逐項結論

### 1. 正確性 —— parser / normalize / diff ✅

實跑四組邊界案例（`app/iec.py:_grab_object` 的字串 / 跳脫狀態機）：

| 案例 | 結果 |
|---|---|
| 字串內含 `{` `}`（`"A{B}C"`）| ✅ 正確切出，未被內層括號騙走 |
| 字串內含跳脫引號（`"say \"hi\" }"`）| ✅ 正確 |
| 字串以反斜線結尾（`"path\\"`）| ✅ 正確 |
| HTML entity（`&quot;`）| ✅ `html.unescape` 後正確 |

`_edition_sort_key`（`iec.py:114-122`）：edition 無法轉 float → 記 `0.0` 排最後。
實測「`edition:"x"` 但日期最新」的惡意輸入 → `current_reference` 仍取到正確的 `GOOD`，
**⛔ 未被非數字 edition 騙成最新版**。

`diff()`（`iec.py:159-178`）只比 `COMPARED_FIELDS`，**刻意排除 `checked_at`** ——
有 `test_checked_at_not_compared` 守著（否則每次都會誤報有更新）。

### 2. D8 核心不變量 —— `/api/check` 任何路徑都不寫 baseline ✅

逐行 grep 確認：`app/main.py` 全檔只有兩處寫檔 ——
`write_baseline` 在 **:127**（`_run_set_baseline` 內，唯一）、`write_last_check` 在 **:182**（`_run_check` 內）。
`_run_check` 的三條返回路徑（`no_baseline` / `error` / `updated|no_update`）**無一觸及 baseline**。
測試 `test_check_never_overwrites_baseline` 以 sha 前後比對守住。

### 3. 節流的鎖 —— ❌ **找到真問題，已修**（見 Finding #1）

### 4. 原子寫入 ✅

實測 `store._write_json`：
- 成功後檔案模式 `0o600`（`mkstemp` 預設）—— 只有容器內 app 讀得到
- **序列化失敗後殘留暫存檔 = 無**（`except` 分支的 `os.unlink` 有效）
- **失敗後原檔仍可讀**（`os.replace` 尚未執行 → 舊內容完整）

### 5. 前端 XSS ✅（含一處防禦性補強，Finding #2）

- 所有插值最終都經 `esc()` / `val()`；`explode()`（`index.html:158-186`）雖然用未逃脫的
  IEC 資料組字串，但那些字串**在 `render()` 內才被 `val()` → `esc()` 輸出**，逃脫發生在輸出點 → 安全。
- **無任何插值落在 HTML 屬性內**（grep `(href|src|onclick|style|class)="[^"]*\$\{` 只命中 `class="verdict ${meta.cls}"`，
  而 `meta.cls` 恆來自檔內字面對照表）。
- Jinja2 對 `.html` 樣板**預設 autoescape** → 上半部 `{{ baseline.* }}` 安全。
- `refreshPanel()` 的 `DOMParser` 解析的是**本站自己的頁面**，且 `DOMParser` **不執行 script** → 安全。

### 6. 部署設定 ✅（含一處補強，Finding #3）

三邊一致：`Dockerfile` `EXPOSE 8000` + `--bind 0.0.0.0:8000` → compose `"172.17.0.1:2000:8000"` → nginx `server 172.17.0.1:2000;`。
`.dockerignore` 未排除 `app/`（`COPY app ./app` 需要它）✅。

### 7. 測試 ✅

33 條（新增併發回歸後）。D8 不變量、error 不覆寫、解析失敗不誤報成 no_update、
節流 per-action、`no_baseline` 不被快取 —— 皆有對應測試且**測的是行為不是實作細節**。

## Findings

| # | 嚴重度 | 檔案:行 | 問題 | 處置 |
|---|---|---|---|---|
| 1 | **中** | `app/main.py:66-88`（修前）| `_throttled()` 在**持有全域 `_lock`** 的情況下呼叫 `fn()`，而 `fn` 內含最長 **30 秒**的對外請求。gunicorn 是 `--workers 1 --threads 2` → 另一條 thread **連讀快取都會被卡住整整 30 秒**，兩個動作互相癱瘓 | ✅ **已修**：改 **per-key 鎖**（`_lock_for(key)`）。同動作併發 → 後到的等前一個做完拿快取（不重複打 IEC）；不同動作 → 互不阻擋。補回歸測試 `test_actions_do_not_block_each_other`（用 Event 卡住抓取、驗另一動作仍能立刻回應）|
| 2 | 低 | `app/templates/index.html:197`（修前）| `${meta.label}` 未逃脫。fallback 分支的 `label` = 伺服器回的 `status` 字串。目前 status 值域固定、**非** IEC 資料，實際不可利用 | ✅ **已修**：改 `esc(meta.label)`（防禦性、不假設來源可信）|
| 3 | 低 | `.dockerignore` | 未排除 `.venv*/`（本機測試用 venv，約數十 MB）。VPS 是 fresh clone 故當下無影響，但本機 `docker build` 會把它塞進 build context | ✅ **已修**：加 `.venv*/` |

## 觀察區（⚠️ 非 finding）

1. ⚠️ `--workers 1` 是 D5 節流正確性的**前提**（節流狀態在程序記憶體內）。若日後有人為了效能改成多 worker，節流會各自為政、對 IEC 的請求量變成 N 倍。`Dockerfile:20-22` 有註解說明，但**沒有機制擋**。
2. ⚠️ `iec.py` 的 `DEFAULT_URL` 寫死。v1 需求就是只追一個目標（issue #1 `## Business Rules`），故不列 finding；未來要多目標時這裡是第一個要動的點。
3. ⚠️ 基準檔 `0600` + 容器內 app 使用者 —— 若日後改用非 root 使用者跑容器、又沿用既有 volume，可能讀不到舊檔。目前 image 未切使用者，無影響。

## VERDICT: REQUEST_CHANGES → 三條全數修正後 **PASS**
