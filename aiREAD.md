# aiREAD.md — small_dick_crawler

> AI / human onboarding 指南。先讀 `CLAUDE.md`（含 Framework Entry + Step 0 bootstrap + 紅線）；
> 本檔負責結構 / dev loop / 常見任務細節。

## 1. 你在哪裡

`small_dick_crawler` 是**測試用途的爬蟲工具 repo**：拿來練 / 驗爬蟲寫法與抓取流程。
獨立 repo，不被任何 repo 引用、也不引用其他 infra repo 的 code；只 pointer 母框架 standards。

**現況（2026-09-04）**：第一個工具已上線 —— `https://smalldick.etbiss.com`，
IEC publication 85813 的版本檢查頁（issue #1）。

## 2. 規範來源 (SSoT)

### Framework / Cross-repo

- **Framework 母規範** + **Lifecycle SSOT** — 見 `CLAUDE.md ## Framework Entry` 的 9-step read order
  （不在本檔重述，per `ssot_vs_guide.md` Tier 分級）
- **使用 framework-read skill 自動跑完 9 步驟** — 見
  `~/projects/project_maker/skills/framework-read/SKILL.md` + 本 repo `CLAUDE.md > Step 0 — Bootstrap`

### Repo-local

- 本 repo 目前**無自有業務 SSOT**。有了再落 `docs/ssot/<domain>.md`
  （落點契約 canonical = `~/projects/project_maker/standards/repo_ssot_layout.md §5`）。

### Deploy contract

不適用 —— 本 repo runtime **不讀** `project_maker/standards/*`，故無
`scripts/deploy_preflight.sh`（per `convergence_framework.md §6.5`）。

## 3. 專案結構

```
small_dick_crawler/
├── README.md                 # 一句話定位
├── CLAUDE.md                 # 規範 entry + Framework Entry block + 紅線
├── aiREAD.md                 # 本檔
├── aiPJINDEX.md              # 專案索引
├── app/                      # Flask app
│   ├── iec.py                #   抓取 + 解析 + 正規化 + 比對
│   ├── sources.py            #   檢查來源的唯一定義（名稱 + 連結；樣板與 CSV 共用）
│   ├── store.py              #   baseline.json / last_check.json 的 atomic 讀寫
│   ├── export.py             #   檢查結果 → CSV（stdlib csv、UTF-8 BOM）
│   ├── main.py               #   GET / + POST /api/baseline + POST /api/check + GET /api/export.csv + /healthz
│   └── templates/index.html  #   單頁前端（零框架、零 CDN）
├── tests/                    # pytest（fixture 離線測、⛔ 不連外網）
├── deploy/nginx/             # smalldick.conf + smalldick-temp.conf（部署時複製到 VPS）
├── Dockerfile
├── docker-compose.yml        # 本機開發（port 21001）
├── docker-compose.prod.yml   # VPS（publish 172.17.0.1:2000）
├── requirements.txt
├── active/                   # 進行中的 plan
├── archived/                 # 已 ship 的 plan
└── reviews/                  # self-review sidecar（plan r1/r2、code r1）
```

## 4. 紅線（動手前 sense check）

| ❌ 禁止 | 為什麼 |
|--------|--------|
| 抓需要登入 / 明令禁止爬取的目標、繞過反爬機制 | 測試場不做越界抓取 |
| commit credential / cookie / token / 抓下來的原始資料 | repo 是公開協作面、資料不該進版控 |
| 對目標站點高頻打點 | 測試一律低頻 + rate limit |
| 讓產品 repo 依賴本 repo | 本 repo 是測試場、無穩定性承諾 |
| 沒 issue 就開始寫 plan / 寫 code | issue-first（`issue_backlog_workflow.md` R1）|

## 5. 執行環境

| 項目 | 值 |
|---|---|
| **port BASE** | **21000**（登錄追蹤於 `ett-et/project_maker#375`；canonical 表在 `issue_backlog_workflow.md` R2）|
| dev port | `21000` |
| feat port | `21000 + (issue# mod 1000)` —— e.g. issue #1 → `21001` |
| 正式站 | `https://smalldick.etbiss.com`（VPS `157.230.34.164`，容器 publish 在 `172.17.0.1:2000`）|

## 6. 開發 loop

```bash
# 本機直接跑（不用 Docker）
python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt
SMALLDICK_DATA_DIR=/tmp/smalldick-data ./.venv/bin/python -m gunicorn app.main:app \
  --bind 127.0.0.1:21001 --workers 1 --threads 2

# 本機用 Docker 跑
docker compose up -d --build          # → http://localhost:21001

# 測試（59 條、不連外網）
./.venv/bin/python -m pytest -q
```

⚠️ **`--workers 1` 是節流正確性的前提**（節流狀態存在程序記憶體內）。改成多 worker 會讓
每個 worker 各自為政、對 IEC 的請求量變成 N 倍。
⚠️ **同一條紅線也綁著「下載結果」的匯出快照**（issue #3 D2：存記憶體、⛔ 不落檔）——
多 worker 會讓「檢查完按鈕該亮」變成擲骰子（請求可能落到沒有該快照的 worker）。

## 7. 部署

```bash
ssh etchai-vps
cd /opt/small_dick_crawler && git pull
docker compose -f docker-compose.prod.yml up -d --build
# 驗：host 側 + nginx 容器側都要通
curl -s -o /dev/null -w '%{http_code}\n' http://172.17.0.1:2000/healthz
docker exec etchai_nginx wget -qO- http://172.17.0.1:2000/healthz
```

nginx 設定住 `deploy/nginx/`，部署時複製到 VPS `/opt/etchai/nginx/conf.d/`
（⛔ 該 nginx 同時服務 etchai / lifetool / ymetc —— reload 前務必先 `nginx -t`）。

## 8. 常見任務

| 任務 | 怎麼做 |
|------|--------|
| 開新工作 | 先開 GitHub issue（`backlog` → 收斂 → 人手翻 `issue-ok`）→ 才寫 plan |
| 寫 plan | `active/<issue>-<slug>/plan_README.md`，格式見 `shared_plan_schema.md` |
| 實作 | `feat/<issue>-<slug>` branch + sibling worktree → PR base `dev` |
| ship | 走 `executor_workflow.md §3.5` 七步 + `§9` 歸檔（在 dev 上做）|

## 9. 不要做的事

- **不要把 gunicorn 改成多 worker** —— 會破壞節流（見 §6）。
- 不要把測試抓下來的資料 commit 進 repo。
- 不要在本 repo 重寫母框架規則 —— 只 pointer。

## 10. 進一步閱讀

- `CLAUDE.md ## Framework Entry` — global standards 入口 + bootstrap
- `~/projects/project_maker/skills/framework-read/SKILL.md` — skill contract
- `~/projects/project_maker/standards/convergence_framework.md` — framework 母規範
- `~/projects/project_maker/standards/issue_backlog_workflow.md` — issue label 狀態機 + R1-R11
- `~/projects/project_maker/standards/executor_workflow.md` — branch / merge / ship 七步
