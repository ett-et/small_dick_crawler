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
| `reviews/` | self-review sidecar（plan r1/r2、code r1）| ❌ |

## 功能模組

| 模組 | 路徑 | 職責 |
|---|---|---|
| **IEC 版本檢查工具** | `app/` | 抓 IEC publication 85813 頁面、解析內嵌版本資料、與基準比對、單頁呈現 |

模組內檔案：

| 檔案 | 職責 |
|---|---|
| `app/iec.py` | `fetch_html` / `extract_blocks`（brace-matching 解析內嵌 JSON）/ `normalize` / `diff` |
| `app/store.py` | `baseline.json` + `last_check.json` 的 atomic 讀寫（mkstemp → fsync → os.replace）|
| `app/main.py` | `GET /`、`POST /api/baseline`（寫基準）、`POST /api/check`（⛔ 不寫基準）、`GET /healthz`；per-action 節流 |
| `app/templates/index.html` | 單頁前端：基準面板 + 兩顆按鈕 + 判定說明 + 差異表（零框架、零 CDN）|

## 對外服務

| 網址 | 狀態 | 部署 |
|---|---|---|
| `https://smalldick.etbiss.com` | 上線（2026-09-04）| VPS `157.230.34.164`，容器 `smalldick_web`，經該機共用 `etchai_nginx` 反代 |

## 業務 SSOT

**無** —— 有了再落 `docs/ssot/<domain>.md`（per `repo_ssot_layout.md §5`），並在此加一列。

## Plan 現況

| 位置 | 內容 |
|------|---|
| `active/1-iec-publication-version-checker/` | issue #1，待 UAT |
| `archived/` | 0 |
