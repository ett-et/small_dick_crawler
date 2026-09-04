# CLAUDE.md — small_dick_crawler（小老二專用的測試爬蟲工具）

## Framework Entry（先讀母框架，再讀 local docs）

**Step 0 — Bootstrap**（僅在「使用 framework-read skill」前需要；若手讀 9 步驟順序可跳過此步。Per ideaer plan `framework-read-skill-bootstrap`，lenient — 失敗不擋 read body）

使用 skill 前 AI / wrapper 端依序執行：

1. **Ensure symlink installed**（idempotent）：

   ```sh
   mkdir -p ~/.claude/skills
   [ ! -e ~/.claude/skills/framework-read ] && \
     ln -sf ~/projects/project_maker/skills/framework-read ~/.claude/skills/framework-read
   ```

2. **Fast-path verify**（兩條 AND；任一 fail → `rm` + 重 install + 重跑 helper.py 一次）：

   ```sh
   test "$(readlink ~/.claude/skills/framework-read)" = "$HOME/projects/project_maker/skills/framework-read"
   python3 "$HOME/projects/project_maker/skills/framework-read/helper.py" \
     drift-report \
     "$HOME/projects/project_maker/standards/convergence_framework.md"
   ```

3. **取 `last_seen_rules_version`**（primary：取 step 2 helper.py 最終那次 output 解出的 version；helper.py 完全不可用才 fallback regex parse master canonical frontmatter `^version:\s*` line。**不從 skill 自然語言 output 反推**）

4. **寫 / 更新 state file** `~/.claude/skills/.framework-read-state.json`（5 fields：`installed_at` / `source_path` / `symlink_path` / `last_used_at` / `last_seen_rules_version`）。

Bootstrap contract 完整 state machine + primary/fallback 邊界硬規則見
`~/projects/project_maker/skills/framework-read/SKILL.md ## Bootstrap`。

`last_seen_rules_version: null` 是 **valid value**（表示有試讀但 fallback 也 fail），**非 "skipped" sentinel**。

**CWD precondition**：使用 skill 前確認 cwd 在本 repo root，否則下方第 8-9 步 local docs 會 ✗ not found。

---

任意 session / task 開始前，先按以下順序讀取（或「使用 framework-read skill」自動跑完）。
**Canonical read order = `skills/framework-read/SKILL.md ## Read order`（steps 1-9 immutable）；本段是其投影** —— 兩處不一致時以 SKILL.md 為準：

1. `~/projects/project_maker/standards/convergence_framework.md` (master canonical)
2. `~/projects/project_maker/standards/idea_proposal_plan_lifecycle.md`
3. `~/projects/project_maker/standards/shared_plan_schema.md`
4. `~/projects/project_maker/standards/behavioral_constraints.md`
5. `~/projects/project_maker/standards/ssot_registry.md`
6. `~/projects/project_maker/standards/compile_safety_preflight_contract.md`
7. `~/projects/project_maker/standards/wsl_operational_guide.md`
8. 本 repo `CLAUDE.md`
9. 本 repo `aiREAD.md`

**必交 receipt**：讀完輸出 receipt block（格式見 `SKILL.md ## Read receipt`）。

**裁決規則**：global standards > local docs。Local rule 不可重寫 global rule；衝突時以
`project_maker/standards/*` 為準；發現矛盾先指出再做（不悄悄繼續）。

## 身分 / 定位

`small_dick_crawler` 是**測試用途的爬蟲工具 repo** —— 拿來試爬蟲寫法 / 驗證抓取流程，
不是產品 repo、不承載任何事業體營運資料。

- 與其他 repo 的關係：**獨立**，目前不被任何 repo 引用、也不引用任何 infra repo 的 code。
- 只 pointer 母框架 standards（`~/projects/project_maker/standards/*`），不重寫規則。

> **未定（尚未拍板、⛔ 不要當事實引用）**：技術棧（語言 / 爬蟲框架 / 執行方式）、
> 目標站點、資料落點。這些定案前不寫進本檔（per `behavioral_constraints.md §2.8`
> —— 沒有 SSOT 就不臆造）。

## SSOT / 規範來源

- **Framework 母規範** — `~/projects/project_maker/standards/convergence_framework.md`
- **Idea / Proposal / Plan lifecycle** — `~/projects/project_maker/standards/idea_proposal_plan_lifecycle.md`
- **Issue label 狀態機（plan 狀態唯一 SSOT）** — `~/projects/project_maker/standards/issue_backlog_workflow.md §5`
- **plan 格式** — `~/projects/project_maker/standards/shared_plan_schema.md`
- 本 repo 目前**無自有業務 SSOT**；有了再落 `docs/ssot/<domain>.md`
  （per `repo_ssot_layout.md §5`）。

## 紅線

- ⛔ **不抓需要登入 / 明令禁止爬取的目標**，也不繞過反爬機制；只對允許的公開頁面測試。
- ⛔ **不把任何 credential / cookie / token / 抓下來的原始資料 commit 進 repo**
  （測試資料放 `.gitignore` 的路徑或本機）。
- ⛔ **不對目標站點高頻打點** —— 測試一律低頻 + 有 rate limit。
- ⛔ 本 repo 是測試場，**不得被任何產品 repo 依賴**。

## 開發慣例

- **branch flow**：`feat/<issue>-<slug>` → PR base `dev` → `dev` → `main`
  （`dev→main` 由人手 `--ff-only` direct merge、不開 PR，per `executor_workflow.md §5`）。
- **issue-first**：沒 issue 不寫 plan（per `issue_backlog_workflow.md` R1）。
- plan 落 `active/<issue>-<slug>/plan_README.md`，ship 後歸檔 `archived/YYYY/QN/`。

## 專案結構

見 `aiPJINDEX.md`。

## Doc Sync 收尾規則

完成任何命中 `behavioral_constraints.md §2.7` trigger 的 task 時：

1. 跑 doc audit（grep 舊文案 / stale 名詞）
2. final response 必須附 `## Doc Sync Report`
3. **未附 report 視為任務未收尾，需 push back 補上**
