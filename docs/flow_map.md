# small_dick_crawler Flow Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。規則本體（「檢查不得寫基準」「失敗不得當成沒更新」）在 [`ssot/business_logic.md`](ssot/business_logic.md) `§2` / `§4`；「哪個動作綁哪個 endpoint」在 [`ssot/api_contract.md`](ssot/api_contract.md) `§1`。本檔 ⛔ 不重述規則。
> 本檔管「一件事從頭到尾怎麼跑」，特別是**跨檔才看得出來的斷點**。

## 為什麼這張圖存在（痛點留痕）

本 repo 已實際踩過兩個「每個檔案分開看都合理、串起來才壞掉」的缺陷，兩個都在這張圖上：

1. **節流快取跨動作說謊** —— `no_baseline` 沒發過任何對外請求卻被存進節流快取，導致「建立基準後再按檢查，仍回 no_baseline」（plan 變更記錄 2026-09-04；修法 = `_fetched` 旗標，`app/main.py:99`、`:172`）。
2. **全域鎖互相癱瘓** —— `_throttled()` 曾持有單一全域鎖去呼叫含 30 秒對外請求的 `fn()`，另一條 gunicorn thread 連讀快取都被卡 30 秒（`reviews/self-review-code-r1.md` Finding #1；修法 = per-key 鎖，`app/main.py:34-41`）。

## 流程 A：建立 / 更新基準（`POST /api/baseline`）

```
前端 btn-baseline click（index.html:274）
  └─ 兩顆按鈕都 disabled、文案改「抓取中…」（index.html:238-243）
      └─ POST /api/baseline ──▶ _throttled("baseline", _run_set_baseline)   main.py:69, :79
            ├─ 10 秒內重複 ──▶ 回上次結果 + throttled:true       ⛔ 不對外發請求   main.py:89-96
            └─ 否則 _run_set_baseline()                                        main.py:129
                  ├─ _fetch_snapshot()                                          main.py:104
                  │     ├─ requests.get(timeout=30)  失敗 ──▶ status=error「抓取失敗」⛔ 不寫基準
                  │     ├─ extract_blocks 失敗       ──▶ status=error「解析失敗」⛔ 不寫基準
                  │     └─ 成功 ──▶ normalize + checked_at
                  ├─ previous = read_baseline()                                 main.py:136
                  ├─ established_at = checked_at                                main.py:137
                  ├─ diff(previous, snapshot)  ← 只為了訊息文案「有 N 個欄位不同」  main.py:139
                  └─ write_baseline(snapshot)   ★ 全 repo 唯一寫基準處            main.py:140
                        └─ status=baseline_set  +  changes[]
  └─ 前端 render() ──▶ refreshPanel()  重抓 GET / 換掉面板與按鈕狀態   index.html:248-250, :260
```

## 流程 B：檢查版本（`POST /api/check`）

```
前端 btn-check click（index.html:273，無基準時該鈕 disabled）
  └─ POST /api/check ──▶ _throttled("check", _run_check)                main.py:74, :79
        └─ _run_check()                                                  main.py:161
              ├─ baseline = read_baseline()                              main.py:164
              │     └─ None ──▶ status=no_baseline ＋ _fetched:False     main.py:166-173
              │                  ★ ⛔ 不進節流快取（沒發過對外請求）      main.py:99
              ├─ _fetch_snapshot()  失敗 ──▶ status=error   ⛔ 不寫任何檔
              ├─ diff(baseline, snapshot)  比 5 欄                        main.py:179
              │     ├─ changes 非空 ──▶ status=updated
              │     └─ changes 空   ──▶ status=no_update
              └─ write_last_check({checked_at, status, change_count})     main.py:195
                    ★ ⛔ 任何路徑都不碰 baseline.json
```

## 主要不變量（跨檔才看得出來）

| 不變量 | 靠什麼守 | 測試 |
|---|---|---|
| `/api/check` 任何路徑都不寫基準 | `_run_check` 三條 return 皆不呼叫 `write_baseline` | `tests/test_api.py::test_check_never_overwrites_baseline` |
| 更新訊號不被自動清除 | 同上（不覆寫 → 下次仍 diff 出同樣差異）| `tests/test_api.py::test_set_baseline_acknowledges_the_update` |
| 解析失敗 ≠ 沒有更新 | `extract_blocks` 拋 `ParseError` → `_fetch_snapshot` 轉 `status=error` | `tests/test_api.py::test_parse_error_is_not_silently_no_update` |
| 失敗不覆寫基準 | `_run_set_baseline` 在 `write_baseline` **之前** return err（`main.py:133-134`）| `tests/test_api.py::test_error_does_not_overwrite_baseline` |
| 沒發過請求的結果不進快取 | `_fetched` 旗標（`main.py:99`）| `tests/test_api.py::test_no_baseline_is_not_cached_by_throttle` |
| 兩個動作互不阻擋 | per-key 鎖 `_lock_for()`（`main.py:34-41`）| `tests/test_api.py::test_actions_do_not_block_each_other` |

## 併發模型（斷點最集中處）

- gunicorn **`--workers 1 --threads 2`**（`Dockerfile:21-22`、`docker-compose.yml:17-19`）。
- 節流狀態存在**程序記憶體**（`app/main.py:34-36`）→ ⚠️ **`--workers 1` 是節流正確性的前提**，改多 worker 會讓對 IEC 的請求量變成 N 倍。**code 內只有註解、⛔ 沒有機制擋**。
- 同一動作併發 → 後到者等前一個做完、直接拿快取（不重複打 IEC）；不同動作 → 互不阻擋。
- 多人同時寫基準 → 靠 `os.replace` 原子換名，最後一個贏、⛔ 不會寫出半截檔（`app/store.py:55`）。

## 前端刷新的隱性依賴

`refreshPanel()` 用 `fetch(location.pathname)` 重抓整頁、再用 `DOMParser` 撈三個節點的內容塞回去（`index.html:260-270`）。
⚠️ 它依賴 `#baselinebox` / `#lastcheck` / `#btn-check` / `#btn-baseline` 這四個 id 在伺服器樣板中存在；改樣板結構會**靜默**打壞刷新（`catch` 吞掉錯誤、`:269`）。
⚠️ 送出的 `X-Panel: 1` header **伺服器端無人讀取**（`app/main.py` 全檔無此字串）—— 是無作用的殘留，不影響行為。
