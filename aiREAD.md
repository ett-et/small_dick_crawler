# aiREAD.md — small_dick_crawler

> AI / human onboarding 指南。先讀 `CLAUDE.md`（含 Framework Entry + Step 0 bootstrap + 紅線）；
> 本檔負責結構 / dev loop / 常見任務細節。

## 1. 你在哪裡

`small_dick_crawler` 是**測試用途的爬蟲工具 repo**：拿來練 / 驗爬蟲寫法與抓取流程。
獨立 repo，不被任何 repo 引用、也不引用其他 infra repo 的 code；只 pointer 母框架 standards。

**現況（2026-09-04）**：repo 剛 bootstrap 完成，**只有文件骨架、尚無任何程式碼**。

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
├── README.md        # 一句話定位
├── CLAUDE.md        # 規範 entry + Framework Entry block + 紅線
├── aiREAD.md        # 本檔
├── aiPJINDEX.md     # 專案索引
├── active/          # 進行中的 plan（active/<issue>-<slug>/plan_README.md）
└── archived/        # 已 ship 的 plan（archived/YYYY/QN/）
```

程式碼目錄尚未建立 —— 技術棧未拍板（見 `CLAUDE.md ## 身分 / 定位` 的「未定」段）。

## 4. 紅線（動手前 sense check）

| ❌ 禁止 | 為什麼 |
|--------|--------|
| 抓需要登入 / 明令禁止爬取的目標、繞過反爬機制 | 測試場不做越界抓取 |
| commit credential / cookie / token / 抓下來的原始資料 | repo 是公開協作面、資料不該進版控 |
| 對目標站點高頻打點 | 測試一律低頻 + rate limit |
| 讓產品 repo 依賴本 repo | 本 repo 是測試場、無穩定性承諾 |
| 沒 issue 就開始寫 plan / 寫 code | issue-first（`issue_backlog_workflow.md` R1）|

## 5. 開發 loop

尚未建立（無程式碼、無測試框架）。定案第一個技術棧時，在此補
「安裝 → 跑 → 測」三行指令，並同步 `aiPJINDEX.md`。

## 6. 常見任務

| 任務 | 怎麼做 |
|------|--------|
| 開新工作 | 先開 GitHub issue（`backlog` → 收斂 → 人手翻 `issue-ok`）→ 才寫 plan |
| 寫 plan | `active/<issue>-<slug>/plan_README.md`，格式見 `shared_plan_schema.md` |
| 實作 | `feat/<issue>-<slug>` branch + sibling worktree → PR base `dev` |
| ship | 走 `executor_workflow.md §3.5` 七步 + `§9` 歸檔（在 dev 上做）|

## 7. 不要做的事

- 不要在沒拍板技術棧前先建 `src/` / `pyproject.toml` / `package.json`（避免預設一個沒人選過的棧）。
- 不要把測試抓下來的資料 commit 進 repo。
- 不要在本 repo 重寫母框架規則 —— 只 pointer。

## 8. 進一步閱讀

- `CLAUDE.md ## Framework Entry` — global standards 入口 + bootstrap
- `~/projects/project_maker/skills/framework-read/SKILL.md` — skill contract
- `~/projects/project_maker/standards/convergence_framework.md` — framework 母規範
- `~/projects/project_maker/standards/issue_backlog_workflow.md` — issue label 狀態機 + R1-R11
- `~/projects/project_maker/standards/executor_workflow.md` — branch / merge / ship 七步
