# small_dick_crawler Data Model Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。canonical 永遠是 code（`app/store.py` + `app/iec.py:123-166`）。
> 「該保存什麼 / 誰能寫」的**規則本體**在 [`ssot/business_logic.md`](ssot/business_logic.md) `§2` / `§6` —— 本檔 ⛔ 不重述規則，只記現在的形狀。

## ⛔ 沒有資料庫

無 DB、無 ORM、無 migration、無 schema 檔。持久層 = **兩個 JSON 檔**，落在 `SMALLDICK_DATA_DIR`（預設 `/data`，`app/store.py:20`）：

| 檔名 | 誰寫 | 何時寫 | 出處 |
|---|---|---|---|
| `baseline.json` | **只有** `POST /api/baseline` | 抓取 + 解析成功後 | `app/store.py:21`、`app/main.py:140`（全檔唯一呼叫）|
| `last_check.json` | **只有** `POST /api/check` | 比對完成後（失敗 / 無基準時不寫）| `app/store.py:22`、`app/main.py:195-202` |

- 皆為**單筆、覆寫式** —— ⛔ 不留歷史、不累積。
- 寫入為原子操作：同目錄 `mkstemp` → `json.dump(sort_keys=True)` → `flush` → `fsync` → `os.replace`；失敗時刪暫存檔並拋出，**原檔完整**（`app/store.py:41-61`）。
- 讀取寬鬆：檔不存在、JSON 壞掉、OSError、或頂層不是 dict → 一律回 `None` = 「當作沒有」（`app/store.py:29-38`）。
- 檔案模式 `0600`（`mkstemp` 預設）；prod 由 named volume `smalldick_data` 掛上、容器 rebuild 不掉（`docker-compose.prod.yml:21-22`、`:27-28`）。

## Snapshot（`baseline.json` 的形狀）

由 `iec.normalize()` 產生（`app/iec.py:123-166`），寫入前由 `_run_set_baseline` 補兩個時間欄（`app/main.py:125`、`:137`）：

| 欄位 | 型別 | 來源 | 參與比對？ |
|---|---|---|:---:|
| `source_url` | str | `iec.DEFAULT_URL`（寫死）| ❌ |
| `current_reference` | str \| null | `lifecycles` 中 edition 最大者的 `main.reference` | ✅ |
| `current_edition` | str \| null | 同上 `main.edition` | ✅ |
| `current_publication_date` | str \| null | 同上 `main.publication_date` | ✅ |
| `lifecycle_entries` | list[obj] | `lifecycles` 全部條目，每筆 `{key, reference, edition, publication_date, status}`，已排序 | ✅ |
| `under_development` | obj \| null | `underDevelopmentProduct` 的 `{reference, edition, stage, status, forecast_pub_date}`；缺席 / 空物件 → `null` | ✅ |
| `checked_at` | str (ISO8601, local tz) | `iec.now_iso()` | ❌ **刻意排除** |
| `established_at` | str | = 寫入當次的 `checked_at`（只有 baseline 檔有）| ❌ |

**參與比對的五欄 canonical = `app/iec.py:170-176` 的 `COMPARED_FIELDS`。** 中文標籤對照在 `app/iec.py:178-184`。

## `last_check.json` 的形狀

只有三個欄位（`app/main.py:196-200`）：`checked_at`（ISO8601）、`status`（`updated` / `no_update`）、`change_count`（int）。
⚠️ **失敗（`error`）與 `no_baseline` 不會寫這個檔** —— 檔內看到的永遠是「上一次成功比對」，不是「上一次按過檢查」。

## 關聯

⛔ 無 FK、無 join。唯一的關聯是**時間軸上的一組比較**：

```
baseline.json（上一次被人明示確認的現況）
        │
        └── iec.diff(baseline, snapshot) ── 逐欄比 5 個欄位 ──▶ changes[]
                    ▲                                            │
        現在抓到的 snapshot（不落檔）                    寫入 last_check.json（只記結果摘要）
```

## 存取邊界（現況）

- **基準是全站共用的單一份**：無登入、無 per-user 資料 → 任何訪客按下「更新基準」都會覆寫所有人看到的基準（issue #1 `## Permission` 明示 v1 接受）。
- 抓回的原始 HTML **不落地**，只留解析後的欄位（`app/main.py:104-126` 用完即丟）。
- 基準檔內 ⛔ 無任何憑證 / secret。

## 改欄位時的隱性代價（⚠️ 現況觀察）

`COMPARED_FIELDS` 或 snapshot 欄位一改，**既有的 `baseline.json` 就會與新 snapshot 逐欄不等** → 下一次檢查必然回報「有更新」（假陽性）。此處無 migration 機制可依靠，處置屬 per-change 判斷（per `living_spec_maintenance.md §8` 第 11 列恆現算）。
