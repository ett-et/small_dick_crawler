---
classification: none
verdict: PASS
round: 1
reviewer: inline 自審（同一個 session，⛔ 非獨立 sub-reviewer —— 誠實界定見下）
date: 2026-09-05
target: git diff origin/dev...HEAD（issue #3 全部實作 + plan）
---

# code self-review r1 — issue #3 檢查結果匯出 CSV

## ⚠️ 誠實界定：reviewer 獨立性

本輪是**寫 code 的人審自己的 code**，比獨立 sub-reviewer 弱 —— 看不見自己的盲點。
沿用 issue #1 `reviews/self-review-code-r1.md` 的補償做法：**每一項都做成可執行的驗證**
（實跑、實 grep、把結論釘成回歸測試），而不是用讀的下結論。證據附在各項後面。

真正的獨立 review 由 PR 上的 code review gate 承擔。

## 逐項結論

### 1. D1（只有「檢查版本」讓按鈕亮）✅

逐行確認 `_export` 的**所有寫入點**：`app/main.py` 全檔只有兩處會動它 ——
`_set_export()`（只被 `_run_check` 呼叫兩次）與 `_clear_export()`（只被 `index()` 呼叫）。

```
$ grep -n "_set_export\|_clear_export" app/main.py
（`_run_check` 的 error 路徑 + 成功路徑各一次；`index()` 一次；其餘皆為定義）
```

`_run_set_baseline()` 全函式 **⛔ 未出現任何 `_export` 字樣**（含它自己的 error 路徑）。
釘樁測試：`test_baseline_never_enables_download`（含失敗路徑）。

### 2. ⚠️ 設計期攔截到的一個會讓功能完全不動的陷阱

既有前端在每次成功動作後會呼叫 `refreshPanel()`，它會**再打一次 `GET /`**
（`templates/index.html`，帶 `X-Panel: 1`）。若 D2 的「`GET /` 清除」寫成無條件，
**檢查完的下一個 request 就把匯出清掉 → D1「檢查後按鈕變亮」根本無法成立**，
而且是那種「本機隨手點一下才會發現」的失敗。

處置：`X-Panel: 1` 豁免（plan I2），並把它釘成回歸測試
`test_panel_refresh_does_not_clear_export`（斷言面板刷新後按鈕**仍然亮著**）。

這條不是 review 抓到的 bug —— 是**讀既有 code 時先攔下的**，記在這裡是因為它值得被後人看見。

### 3. D2（記憶體、不落檔、重整清空、同頁可重複下載）✅

| 子條件 | 驗證 |
|---|---|
| ⛔ 完全不落檔 | `test_export_does_not_write_any_file`：下載前後 data dir 內容完全相同，且只有既有的兩個 json |
| 重整後清空 | `test_index_clears_export`：`GET /` 後按鈕 disabled + `/api/export.csv` 回 409 |
| 同頁可重複下載 | `test_download_twice_in_same_page`：兩次都 200 且 bytes 完全相同 |
| 匯出路徑不碰 store | `grep -n "store\." app/main.py` → 只在 `index` / `_run_set_baseline` / `_run_check` 出現，`export_csv` 內 0 次 |

### 4. D3 + D5（失敗列寫原因、且照樣有名字連結）✅

`test_error_row_keeps_name_and_writes_reason` 直接斷言四欄的實際值；
另補 `test_error_without_message_still_not_blank` 守「訊息意外缺席時也不留白」的下限。

失敗文案**沿用 `_fetch_snapshot()` 既有的人話訊息**（`抓取失敗：…` / `解析失敗：…`）——
⛔ 沒有另造一套，否則 CSV 會跟頁面上顯示的不一致（第二份真相）。

### 5. D4（CSV + BOM + 零新相依）✅

```
$ git diff origin/dev -- requirements.txt requirements-dev.txt | wc -l
0
$ grep -n "^import\|^from" app/export.py
csv / io / datetime（全 stdlib）+ from . import sources
```

`test_csv_starts_with_utf8_bom` 斷言 `b"\xef\xbb\xbf"` 開頭。

### 6. D5 的「上提」是不是真的只有一份 ✅

最強的那條斷言在 `test_target_name_is_shared_between_page_and_csv`：
除了驗「頁面有、CSV 也有」，還**反向斷言樣板檔裡不得再出現該名稱字面量** ——
未來有人手癢把名字寫回 HTML，測試會紅。

網址沒有被複製一份：`test_source_url_is_not_a_second_copy` 用 `is` 斷言
`sources.SOURCES[0]["url"] is iec.DEFAULT_URL`（同一個物件，不只是相等）。

### 7. 既有紅線回歸 ✅

| 紅線 | 驗證 |
|---|---|
| `POST /api/check` 任何路徑不寫 baseline | 既有 `test_check_never_overwrites_baseline` 仍綠；本次未動 `_run_check` 的寫檔邏輯 |
| 下載 ⛔ 不對 IEC 發請求 | `test_download_does_not_hit_iec`：計數器在兩次下載前後不變 |
| 零 CDN / 零前端框架 | `grep -rE "https?://(cdn\|unpkg\|jsdelivr\|fonts\.googleapis)" app/ \| wc -l` → `0` |
| gunicorn `--workers 1` | `Dockerfile` 未動；aiREAD §6 補了一段說明「這條紅線現在也綁著匯出」 |
| 失敗不得被誤報成「沒有更新」 | 既有 `test_parse_error_is_not_silently_no_update` 仍綠；CSV 的 `error` → `檢查失敗`，⛔ 不映射到 `沒有更新` |

### 8. 節流互動 ✅（這是最容易寫錯的一處）

`export_ready` **在 `_throttled()` 包裝層即時算**、⛔ 沒有進被快取的 result dict。
釘樁：`test_export_ready_is_not_stale_when_throttled` —— 檢查 → 重整（清掉匯出）→ 再檢查（走快取），
斷言 `throttled is True` **且** `export_ready is False`。若旗標被一起快取，這條會紅。

這是 issue #1 那次「`no_baseline` 被誤快取」教訓的同一類坑，刻意先擋。

## Findings

| # | 嚴重度 | 檔案 | 問題 | 處置 |
|---|---|---|---|---|
| 1 | **中** | `app/export.py` | **CSV 公式注入**：「最新版次」欄的內容有一部分來自**外部抓回來的 IEC 頁面**（reference / edition 字串）。Excel 會把 `=` `+` `-` `@` 開頭的儲存格當**公式**執行 —— 而本功能的整個重點就是「拿去 Excel 開」，等於把外部內容直接餵進去 | ✅ **已修**：加 `_neutralize()`（單引號前綴強制成文字），四欄全過。補 `test_formula_injection_is_neutralized` + `test_normal_values_are_untouched`（確認正常值 ⛔ 不被加引號、不破壞 D5「與畫面完全一致」）|
| 2 | 低 | `tests/test_api.py` | **我自己的改動弱化了一條既有測試**：`test_check_button_disabled_without_baseline` 原本只斷言「整頁字串裡有 `disabled`」。加了第三顆（預設 disabled 的）下載鈕之後，即使 btn-check **沒有** disabled 這條也會綠 —— 測試名字說的事情不再被驗到 | ✅ **已修**：把斷言範圍收斂到 `id="btn-check"` 自己那個 tag 內 |
| 3 | 低 | `app/main.py` | 「建立／更新基準」對**已存在**的匯出快照的處置（不清除）沒有任何測試釘住 → 未來重構可能無聲改變，而 D1/D2 都沒直接規定這一格 | ✅ **已修**：補 `test_baseline_does_not_clear_an_earned_export`，並在測試 docstring 寫明推導依據（D2 明列的清除觸發**只有** `GET /`）|

## 觀察區（⚠️ 非 finding、未修）

1. ⚠️ **`X-Panel: 1` 豁免是用戶端可控的 header 決定伺服器副作用**。理論上可偽造。
   誠實界定影響面：最壞結果 = 某人自己的匯出快照晚一點 / 早一點被清掉；
   **沒有資料外洩、沒有寫入、沒有對 IEC 發請求**（`_export` 內只有本來就顯示在同一頁上的資訊）。故接受。
2. ⚠️ 下載用 `window.location.href` 導頁。若 race 到 409（例如另一個分頁先重整過），
   瀏覽器會顯示一頁 JSON 錯誤、使用者要按上一頁。按鈕暗著時不可能觸發、單人工具，未修。
   要修的話是「先 `fetch` 再 blob 下載」，複雜度明顯上升、收益不相稱。
3. ⚠️ **`GET /` 帶副作用**（D2 丙的必然代價）。已在三處明寫：issue #3 `## Decisions`、
   plan `## Decisions` I2、`app/main.py` `index()` 的註解。⛔ 不假裝沒這回事。
   若 UAT 認為不可接受 → 走 plan `## Checkpoints` C1 停手上浮。
4. ⚠️ `--workers 1` 這條紅線現在綁著**三**件事（節流正確性 / 匯出快照 / 按鈕亮暗），
   已在 `aiREAD.md §6` 補警告，但**仍然沒有機制擋**（沿用 issue #1 code review 的同一條觀察）。
5. ⚠️ `plan_README.md` 224 行，超過全域 CLAUDE.md「超過 80 行主動拆檔」的建議。
   沿用本 repo 既有先例（`archived/2026/Q3/1-.../plan_README.md` 亦為單檔、逾 250 行、已通過 review 並 shipped）；
   且拆檔會讓 core 8 sections 散落。若 reviewer 要求拆，照拆即可。
6. ⚠️ `app/sources.py` 目前是硬編碼常數。多來源票要動的第一個點就是它 ——
   刻意留成「加一筆資料就好」的形狀，但 ⛔ 沒有做來源管理（issue #3 `## 明確不做`）。

## 測試

```
$ env -u SMALLDICK_THROTTLE_SECONDS -u SMALLDICK_DATA_DIR ./.venv-test/bin/python -m pytest -q
...........................................................              [100%]
59 passed in 0.25s
```

| 檔案 | 條數 | 變化 |
|---|---:|---|
| `tests/test_iec.py` | 14 | 未動 |
| `tests/test_api.py` | 33 | +14（既有 19 條全綠、其中 1 條被**強化**，見 finding #2）|
| `tests/test_export.py` | 12 | 全新 |
| **合計** | **59** | 基線 33 → 59 |

## VERDICT: PASS

三條 finding 全數在本輪修正並補上回歸測試。⛔ 無未收斂的設計分岔
（classification `none` —— 沒有 arch / scope / env / struct 級的問題）。
