---
classification: none
verdict: PASS
round: 1
reviewer: inline（原派的收尾 sub-agent 兩度被電腦睡眠中斷，見下方誠實界定）
date: 2026-09-05
target: issue #4 —— docs/ssot/ + docs/specs/ + 地圖層 + aiPJINDEX 索引
---

# self-review r1 — repo 級 SSOT 與地圖層

## ⚠️ 誠實界定：本輪 reviewer 獨立性打折

原本派了獨立 sub-agent 收尾，**兩次都在同一點被電腦睡眠中斷**
（`API Error: Your computer went to sleep mid-response`），第二次連一步都沒跑完。

- 依 `behavioral_constraints.md §2.14 觸發前提` + `§2.21`：**外部中斷 ≠ 設計性收斂失敗**
  → ⛔ 未翻 `needs-code-review-check`、⛔ 未計入 3-strike。
- 為不再空轉，改由**同一個 session inline 完成**。**這比獨立 reviewer 弱**。
- **補償**：驗證一律做成**可執行的檢查**（見下），⛔ 不用讀的下結論。
- 本 session 第 3 次外部中斷（前兩次：帳號用量上限、電腦睡眠）。

## 驗證（可執行、非宣稱）

### 1. cite 抽驗 8/8 全中

⛔ 不採信前手 agent 的宣稱，逐條 `sed -n '<行>p'` 實查：

| cite | 期望含 | 結果 |
|---|---|---|
| `app/iec.py:22` | `DEFAULT_URL` | ✅ |
| `app/iec.py:117` | `float(` | ✅ |
| `app/iec.py:143` | `entries.sort` | ✅ |
| `app/store.py:21` | `BASELINE_NAME` | ✅ |
| `app/store.py:22` | `LAST_CHECK_NAME` | ✅ |
| `app/main.py:143` | `baseline_set` | ✅ |
| `app/main.py:168` | `no_baseline` | ✅ |
| `app/templates/index.html:262` | `X-Panel` | ✅ |

### 2. 兩條紅線

| 紅線 | 檢查方式 | 結果 |
|---|---|---|
| `repo_ssot_layout.md §7`：**SSOT ⛔ 不列舉現況** | grep `目前有哪些` / `現有 endpoint` / `清單如下` 於 `docs/ssot/*.md` | ✅ 零命中 |
| `living_spec_maintenance.md §8 (B)`：**地圖只 pointer、⛔ 不重述規則** | grep `SHALL` / `MUST NOT` / `⛔ 不得` 於 `docs/*_map.md` | ✅ 零命中 |

### 3. frontmatter 契約（`repo_ssot_layout.md §6`）

`business_logic.md` / `api_contract.md` 皆帶六欄（`version` / `name` / `scope` / `override` / `change_gate` / `domain_load_trigger`），且**未寫** §6 明禁的 `canonical path`（寫了會漂）。✅
`docs/ssot/README.md` **刻意無 frontmatter** —— 它是索引不是 domain SSOT，檔內已自述。✅

### 4. dangling pointer

`docs/feature_map.md` 末段把 13 視角 ledger 指向 `aiPJINDEX.md ## 地圖層`。
本輪**已建立該段**，pointer 不再懸空。✅ 且 ledger **只存在一處**（feature_map 明寫「⛔ 不重列」）。

## Findings

| # | 嚴重度 | 問題 | 處置 |
|---|---|---|---|
| 1 | 中 | `aiPJINDEX.md` 缺 `## 地圖層`，`feature_map.md` 的 pointer 懸空 | ✅ 已補；ledger 落 `aiPJINDEX.md`（repo 索引正規歸宿），`feature_map.md` 只 pointer |
| 2 | 低 | 頂層佈局表缺 `docs/` 一列 | ✅ 已補 |
| 3 | 低 | 「## 業務 SSOT」仍寫「**無**」 | ✅ 已改為兩列 + 指向七條 domain 判定表 |

## ⚠️ 未處置、交 Human 判斷的兩件事

### (A) 文件量與 code 量幾乎 1:1 —— 這是否過肥？

```
docs/ 合計   723 行（11 檔）
app/  code   773 行
```

issue #4 `## Technical Constraints` 是我自己寫的：「規模很小 → 文件量要與之相稱，⛔ 不為了填格式而膨脹」。**723:773 這個比例，看起來就是它想防的東西。**

**我沒有自行刪減**，理由是逐檔讀過後，內容確實不是填充：

- `deployment_map.md`（86 行）—— 多條「⛔ 不要改成…」的**理由不在 code 裡**，且 blast radius 跨到另外三個租戶。這份最值得留。
- `flow_map.md`（72 行）—— 記的是**兩個已實證的 bug**（節流跨動作快取說謊、全域鎖互相癱瘓），都是「單檔看都合理、串起來才壞」。
- `feature_map.md` 的「明確沒有的能力」段 —— 防止未來的人誤以為某功能存在。

**但「每一份單看都有價值」不等於「合起來的量是對的」。** 縮減是你的決定，不是我的：
**(甲)** 照收 ／ **(乙)** 砍到剩 SSOT + spec + deployment_map ／ **(丙)** 你指定砍哪幾份。

### (B) `api_contract.md` 有 4 條標 `code-only` —— 等於本次**追認**了從未拍板的行為

那 4 條規則**只存在於 code 裡、從來沒有被正式決定過**：

| 條 | 內容 |
|---|---|
| R-A4 | 所有回應**恆回 HTTP 200**（失敗也是）|
| R-A7 | 內部旗標 `_fetched` 不得外洩到回應 |
| R-A8 | `/healthz` 不得依賴外部服務 |
| R-A10 | 前端不自存狀態、一律回頭問後端 |

前手 agent 已誠實標記並在檔內註明「本檔是首次明文化」，⛔ 未假裝是既有決策。

⚠️ **但寫進 SSOT 就等於追認。** 其中 **R-A4 正被 [#5](https://github.com/ett-et/small_dick_crawler/issues/5) `## Open Questions` 2 質疑**
（失敗恆回 200 → 外部監控看不出異常）。**請 Human 逐條確認這 4 條是不是你要的行為**，而不是「當初隨手寫成那樣」。

## VERDICT: PASS

三個 finding 已修；(A)(B) 兩件**明確標為待 Human 判斷**，⛔ 未自行決定。
