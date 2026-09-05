# aiPJINDEX.md — small_dick_crawler 專案索引

> 手寫索引（本 repo 尚未接 `generate_aipjindex.py` 機器生成區塊）。
> 新增頂層目錄 / 檔案時同步本表（per `behavioral_constraints.md §2.7` Doc Sync Gate）。

## 頂層佈局

| 項目 | 放什麼 | 算功能模組？ |
|------|--------|:---:|
| `README.md` | 一句話定位 | ❌ |
| `CLAUDE.md` | 規範 entry（Framework Entry 9-step + 身分 + 技術棧 + 紅線 + 開發慣例）| ❌ |
| `aiREAD.md` | onboarding（結構 / 執行環境 / 開發 loop / 部署 / 常見任務）| ❌ |
| `aiPJINDEX.md` | 本檔 —— 專案索引 | ❌ |
| `app/` | Flask 應用本體 | ✅ |
| `tests/` | pytest 測試（fixture 離線測、⛔ 不連外網）| ❌ |
| `deploy/nginx/` | nginx 反代設定（部署時複製到 VPS `/opt/etchai/nginx/conf.d/`）| ❌ |
| `Dockerfile` | 容器映像定義 | ❌ |
| `docker-compose.yml` | 本機開發（port 21001）| ❌ |
| `docker-compose.prod.yml` | VPS 正式（publish `172.17.0.1:2000`）| ❌ |
| `requirements.txt` / `requirements-dev.txt` | 相依套件（鎖版本）| ❌ |
| `active/` | 進行中的 plan（`active/<issue>-<slug>/plan_README.md`）| ❌ |
| `archived/` | 已 ship 的 plan（`archived/YYYY/QN/`）| ❌ |
| `reviews/` | self-review sidecar（issue #1 plan r1/r2 + code r1、issue #3 r1、issue #4 r1）| ❌ |
| `docs/` | **業務 SSOT（`ssot/`）+ living spec（`specs/`）+ 地圖層（`*_map.md`）** | ❌ |

## 功能模組

| 模組 | 路徑 | 職責 |
|---|---|---|
| **IEC 版本檢查工具** | `app/` | 抓 IEC publication 85813 頁面、解析內嵌版本資料、與基準比對、單頁呈現、檢查結果匯出 CSV |

模組內檔案：

| 檔案 | 職責 |
|---|---|
| `app/iec.py` | `fetch_html` / `extract_blocks`（brace-matching 解析內嵌 JSON）/ `normalize` / `diff` |
| `app/sources.py` | 檢查來源的**唯一一份**定義（名稱 + 連結）—— 樣板與 CSV 共用，⛔ 不各寫一份（issue #3 D5）|
| `app/store.py` | `baseline.json` + `last_check.json` 的 atomic 讀寫（mkstemp → fsync → os.replace）|
| `app/export.py` | 檢查結果 → CSV（stdlib `csv`、UTF-8 BOM、四欄固定順序、一列一來源）；純函式、⛔ 零新相依 |
| `app/main.py` | `GET /`（順帶清匯出快照）、`POST /api/baseline`（寫基準）、`POST /api/check`（⛔ 不寫基準）、`GET /api/export.csv`（⛔ 不打 IEC）、`GET /healthz`；per-action 節流 |
| `app/templates/index.html` | 單頁前端：基準面板 + 三顆按鈕 + 判定說明 + 差異表（零框架、零 CDN）|

## 對外服務

| 網址 | 狀態 | 部署 |
|---|---|---|
| `https://smalldick.etbiss.com` | 上線（2026-09-04）| VPS `157.230.34.164`，容器 `smalldick_web`，經該機共用 `etchai_nginx` 反代 |

## 業務 SSOT（規則本體 —— 「該怎樣」）

落點契約 canonical = `~/projects/project_maker/standards/repo_ssot_layout.md §5`。
**索引與七條 domain 的逐條判定（含五條「不適用 + 為什麼」）見 [`docs/ssot/README.md`](docs/ssot/README.md)。**

| domain | 檔 | 管什麼 |
|---|---|---|
| Business Logic | [`docs/ssot/business_logic.md`](docs/ssot/business_logic.md) | 「有更新」怎麼判、基準（baseline）誰能寫、失敗怎麼算、對目標站點怎麼發請求 |
| API Contract | [`docs/ssot/api_contract.md`](docs/ssot/api_contract.md) | 兩個動作的讀 / 寫語意、`status` 封閉值域、回應必有欄位、節流以旗標表達 |

其餘五條 domain（RBAC / 營運角色 / 職能 / Access Control / Approval Flow）**判定為不適用**，理由逐條記在 `docs/ssot/README.md`，⛔ 不建空殼檔。

## 地圖層（現況投影 —— 「現在長怎樣」）

canonical = `~/projects/project_maker/standards/living_spec_maintenance.md §8`。
⚠️ **與上一段互補不重疊**：SSOT 寫規則、地圖寫現況；單向 pointer `地圖──▶SSOT──▶code`（`repo_ssot_layout.md §7`），⛔ 不互相追。

**living spec**：[`docs/specs/iec_version_check.md`](docs/specs/iec_version_check.md)

**13 種視角的逐項判定**（本表為該 ledger 的 canonical 落點；`docs/feature_map.md` pointer 至此、⛔ 不重列）：

| # | 視角 | 結論 | 理由 |
|---|---|---|---|
| 1 | Feature Map | **落檔** [`docs/feature_map.md`](docs/feature_map.md) | 只有一個功能，但仍是 registry 入口 + Project Scan 首讀，成本近零 |
| 2 | UI / Page Map | **落檔** [`docs/ui_map.md`](docs/ui_map.md) | 單頁，但「檢查版本」按鈕的啟用狀態**橫跨三處**協同決定（Jinja 條件 / `dataset` / `refreshPanel`）|
| 3 | Data Model Map | **落檔** [`docs/data_model_map.md`](docs/data_model_map.md) | 無 ORM ≠ 無資料模型 —— 兩個持久化 JSON 的欄位形狀原本無任何文件記載 |
| 4 | Validation / Constraint | **不落檔** | 無使用者輸入欄位；唯一約束（對外部回應的驗證）＝ living spec `## Behavior` 主體。N=1 時獨立成檔 = 逐字重寫，撞 `§8 (B)`「地圖只 pointer」|
| 5 | Permission Map | **不適用** | 無登入 / 帳號 / 角色 / tenant，全 repo 零 auth code。唯一存取事實（基準全站共用、任何訪客可覆寫）記在 `data_model_map.md` |
| 6 | State Map | **不落檔** | 唯一狀態語意 =「基準有／無 × 與現況一致／不一致」，正是 spec Behavior 主體；5 個 `status` 是**回應分類**不是物件生命週期，已記在 `ui_map.md` |
| 7 | Flow Map | **落檔** [`docs/flow_map.md`](docs/flow_map.md) | 痛點已實證 —— 節流跨動作快取說謊、全域鎖互相癱瘓，兩個 bug 都是「單檔看都合理、串起來才壞」|
| 8 | Event Map | **不適用** | 零 signal / 背景任務 / webhook / 通知 / audit log |
| 9 | Integration Map | **落檔** [`docs/integration_map.md`](docs/integration_map.md) | 唯一外部整合，且是最脆弱的一點（解析對方頁面內嵌 JS 字面量，無版本號、無相容承諾）|
| 10 | Dependency Map | **恆現算不落檔** | `§8` 表第 10 列明訂；本 repo 現算成本近零 |
| 11 | Migration / Backfill | **恆現算不落檔** | `§8` 表第 11 列明訂（per #285）；無 `migrations/`。真正的 backfill 面（改 snapshot 欄位 → 既有 baseline 被誤判成有更新）是 per-change 判斷，已在 `data_model_map.md` 末段留註 |
| 12 | Observability Map | **落檔** [`docs/observability_map.md`](docs/observability_map.md) | 內容薄，但**盲區本身就是有價值的現況** —— 零 log + 失敗回 200 + 不寫紀錄（已開 [#5](https://github.com/ett-et/small_dick_crawler/issues/5)）|
| 13 | Deployment Map | **落檔** [`docs/deployment_map.md`](docs/deployment_map.md) | 本 repo 價值最高 —— 與另外三個租戶共用 nginx、blast radius 跨 repo、多條「⛔ 不要改成…」的理由不在 code 內 |
| — | Living-demo（不佔列）| **不適用** | `frontend_governance.md §12` 針對元件化前端；本 repo 前端是 277 行零框架單檔，showcase 會是那一頁的複製品 |

## Plan 現況

| 位置 | 內容 |
|------|---|
| `active/3-export-check-result-excel/` | issue #3，檢查結果匯出 CSV（進行中）|
| `archived/2026/Q3/1-iec-publication-version-checker/` | issue #1，shipped 2026-09-04 |
