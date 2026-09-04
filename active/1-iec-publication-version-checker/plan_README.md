---
slug: iec-publication-version-checker
title: IEC 標準版本檢查工具 — smalldick.etbiss.com 單頁 check new
created: 2026-09-04
type: LocalPlan
upstream: issue #1
branch: feat/1-iec-publication-version-checker
shipped: false
dev_merged: false
---

# IEC 標準版本檢查工具

## Tracking

Issue: https://github.com/ett-et/small_dick_crawler/issues/1

## Goal

在 `smalldick.etbiss.com` 上線一個單頁工具：一個「check new」按鈕，按下去比對 IEC publication 85813（IEC 62368-1:2023 RLV）的版本資料是否與上次記錄不同，結果顯示在頁面下方。

需求 SSOT = issue #1（本 plan 不重抄需求，只定**怎麼做**）。

## Context

**目標站點現況（實查 2026-09-04）**：

- `curl -s -o /dev/null -w '%{http_code} %{size_download} %{time_total}' https://webstore.iec.ch/en/publication/85813` → `200 494055 0.408`；帶 / 不帶 User-Agent 皆通過。
- `curl https://webstore.iec.ch/robots.txt` → HTTP 200、**body 為空** → 未宣告禁爬規則。
- 版本資料**內嵌於 HTML**，為 Alpine.js 元件的初始資料，形如 `lifecycles: {"v4":{...}}` 與 `underDevelopmentProduct: {"reference":"IEC 62368-1/AMD1",...}`。以 brace-matching 取出後 `json.loads` 可解析成功（本 session 已跑通）。
- `<script type="application/ld+json">` 存在但**內容為空** → 不可作資料來源。
- → **單次 HTTP GET 即可，不需 headless browser。**

**部署環境現況**：

| 項目 | 值 | 來源 |
|---|---|---|
| VPS | DigitalOcean SGP1、`157.230.34.164`、Ubuntu 24.04、**1 vCPU / 2 GB RAM** | `od_vps_ubuntu-s-1vcpu-2gb-70gb-intel-sgp1-01/README.md` |
| 既有租戶 | `etchai.etbiss.com` / `lifetool.etbiss.com` / `ymetc.com`（同一台、同一組 nginx） | 同上 `docs/network.md` |
| 反向代理 | 容器 `etchai_nginx`（`nginx:alpine`），conf 於 `/opt/etchai/nginx/conf.d/` | `etchai/docker-compose.prod.yml:146-163` |
| conf 掛載 | `- ./nginx/conf.d:/etc/nginx/conf.d:ro`（**整目錄** bind-mount） | `etchai/docker-compose.prod.yml:155` |
| TLS | certbot 容器 + `/etc/letsencrypt` volume；ACME challenge → `root /var/www/certbot` | `etchai/nginx/conf.d/etchai.conf:11-13` |
| repo 追蹤的 conf | 只有 `nginx/nginx.conf`、`conf.d/default.conf`、`conf.d/etchai.conf`（`git ls-files nginx`） | `ett-et/etchai` 實查 |
| DNS | Cloudflare；`smalldick` A → `157.230.34.164` 已由 Human 於 2026-09-04 新增（暫「僅限 DNS」） | Human 回報 + `dig` |

**前置依賴**：port BASE 20000 登錄追蹤於 `ett-et/project_maker#375`（未落地前不起 dev/feat port server）。

## Decisions

### D1 — 技術棧：Flask + gunicorn，單一容器

- 規則：後端用 **Python 3.12 + Flask + gunicorn（1 worker、2 threads）**，前端為單一 HTML（無前端框架、無打包工具），全部塞進一個容器。
- 理由：需求是「一個頁面 + 一個 endpoint」。VPS 只有 1 vCPU / 2 GB 且已住三個租戶（issue #1 `## Non-functional` 要求 < 100 MB）。WSGI + gunicorn 與同機 etchai 的既有慣例一致。
- 替代方案：
  - FastAPI + uvicorn（拒絕，原因：非同步能力對單一同步抓取無用，多一層依賴）
  - 純 stdlib `http.server`（拒絕，原因：單執行緒、非 production-grade，省下的依賴不值）
  - headless browser（**拒絕，硬約束**：資料已內嵌於 HTML，且 2 GB RAM 不容許）

### D2 — 抓取與解析：brace-matching 取出內嵌 JSON

- 規則：以 `requests` GET 目標頁（timeout 30s、帶標示身分的 User-Agent），在回傳文字中定位 `lifecycles: {` 與 `underDevelopmentProduct: {`，用**大括號配對**掃出完整 JSON 字串，`html.unescape` 後 `json.loads`。
- 理由：本 session 已實測跑通；比 regex 穩（JSON 內含巢狀大括號，regex 會斷在第一個 `}`）。
- 替代方案：
  - regex 抓 `\{.*?\}`（拒絕：巢狀結構會截斷）
  - HTML parser（拒絕：資料在 JS 字面量裡，不是 DOM 節點）
  - ld+json（拒絕：實查為空）
- **紅線**：`lifecycles` 解析不到 → 判**失敗**，不可靜默當「沒有更新」（issue #1 `## Edge Cases`）。`underDevelopmentProduct` 缺席為**合法**（代表目前無開發中版本）。

### D3 — 基準儲存：單一 JSON 檔 + atomic write + docker volume

- 規則：基準存 `/data/baseline.json`（容器內），對應一個 named volume。寫入用 `tempfile` 同目錄建檔 → `os.replace()` 原子換名。
- 理由：只有一個目標、單機、單 worker → DB 是過度設計（`behavioral_constraints.md §2.4`）。原子換名滿足 issue #1「同時多人按按鈕不得寫壞基準檔」。volume 滿足「容器重建後基準需存活」。
- 替代方案：SQLite（拒絕：為單筆資料引入 schema 與 migration）／存容器內非 volume 路徑（拒絕：重建即消失）

### D4 — 比對邏輯：正規化後整體比對，差異逐欄列出

- 規則：把 `lifecycles` + `underDevelopmentProduct` 正規化成一個穩定結構（dict 排序固定），與基準逐欄比對；任一欄不同即「有更新」，回傳 `{欄位: {before, after}}` 清單。
- 理由：issue #1 `## Business Rules` 的 A/B/C 三訊號**全部**落在這兩包資料裡 → 一次整體比對即可涵蓋三者，不需為每個訊號各寫一段判斷（`§2.4`）。
- 替代方案：分別寫 A/B/C 三段判斷（拒絕：三段程式碼做一件事、且容易漏掉未列舉的欄位變動）

### D5 — 節流：程序內記憶體時間戳，最小間隔 10 秒

- 規則：後端記住上次實際抓取的時間，10 秒內的重複請求直接回上次結果並標示「節流中」，不對 IEC 發新請求。前端在請求進行中停用按鈕。
- 理由：滿足 issue #1「不得對目標站點高頻打點」與 repo 紅線。單 worker → 程序內狀態即足夠。
- 替代方案：Redis / 檔案鎖（拒絕：單 worker 單機，過度設計）

### D6 — nginx 設定檔進 `ett-et/etchai` 版控

- 規則：`smalldick.conf` 以 PR 進 `ett-et/etchai` 的 `nginx/conf.d/`，與 `etchai.conf` 同待遇。
- 理由：Human 於 2026-09-04 拍板「要留底」；且 `conf.d` 是整目錄 bind-mount → 檔案實體必須落在該處才生效。
- 替代方案：直接在 VPS 手寫不進版控（**拒絕**，Human 明示；該做法的既有債另由 `lifetool#10` / `ymes#218` 追蹤）

### D7 — 容器不與 etchai 的 compose 綁在一起

- 規則：本服務用**自己的** `docker-compose.yml`，監聽 host 的 `127.0.0.1:20080`，由 etchai 的 nginx 以 `proxy_pass http://172.17.0.1:20080` 反代。
- 理由：issue #1 `## Non-functional`「本工具故障不得影響同機其他服務」。與既有 `ymetc.com` → `172.17.0.1:8004` 的做法同構（`od_vps_.../docs/network.md`），不是新發明。
- **與 `Port:` line 的關係**：`Port: 20001` 是**驗收者本機**的 UAT port（per `issue_backlog_workflow.md` R2）；`20080` 是 **VPS 上的 host publish port**，兩者不同層、不衝突。
- 替代方案：塞進 etchai 的 compose（拒絕：故障域綁在一起、且要動 etchai 的服務定義而非只加一份 conf）

## Approach

1. **專案骨架**（worktree 內）：`app/`（Flask app + 解析模組 + 模板）、`tests/`、`Dockerfile`、`docker-compose.yml`、`requirements.txt`。
2. **解析模組** `app/iec.py`：`fetch_html(url)` / `extract_blocks(html)` / `normalize(blocks)` / `diff(baseline, current)`。純函式、不碰網路的部分可離線測。
3. **儲存模組** `app/store.py`：`read_baseline()` / `write_baseline(snapshot)`（atomic）。
4. **Flask app** `app/main.py`：`GET /` 回頁面（含上次檢查時間）、`POST /api/check` 回 JSON、`GET /healthz` 回 200。
5. **前端** `app/templates/index.html`：按鈕 + `fetch()` + 結果區塊；無外部 CDN（自帶樣式）。
6. **測試**：用**存下來的真實 HTML fixture** 測解析與比對；不在測試中連外網。
7. **本機驗證**：起容器、按按鈕走完四種結果（已建立基準 / 沒有更新 / 有更新 / 檢查失敗）。
8. **部署**：VPS `git clone` 到 `/opt/small_dick_crawler` → `docker compose up -d` → 確認 `curl 127.0.0.1:20080/healthz`。
9. **nginx**：於 `ett-et/etchai` 開 PR 加 `nginx/conf.d/smalldick.conf`（先只有 :80 + ACME challenge）→ 部署 → 簽發憑證 → 補 :443 區塊 → reload。
10. **收尾**：更新 `aiREAD.md`（執行環境段）+ `aiPJINDEX.md`；`od_vps_.../docs/{services,network}.md` 需同步（跨 repo，需另取得授權或開票）。

### 需決定

（目前無；有新分岔時移入 `## Decisions`）

## Test Strategy

- Unit: yes — 解析（`extract_blocks` / `normalize`）+ 比對（`diff`）+ 儲存（atomic write / 缺檔）以真實 HTML fixture 離線測
- E2E: yes — 以 Flask test client 打 `GET /` + `POST /api/check`（外部抓取以 fixture stub 掉），涵蓋四種結果分支
- UAT: yes — Human 於 `smalldick.etbiss.com` 照 issue #1 `## UAT Checklist` 跑，10 條
- 依據: standards/test_strategy_layering.md

## Checkpoints

| ID | Trigger | Stop condition | User decision needed |
|----|---------|----------------|---------------------|
| C1 | 本機容器跑起來、四種結果都走過一遍 | 停下，把畫面與四種結果貼給 Human 看 | 畫面與文案可不可以，要不要調整再上線 |
| C2 | 要動 `ett-et/etchai` 開 PR 前 | 停下，說明 PR 內容 | 確認跨 repo 動作範圍與時機 |
| C3 | 要動 `od_vps_...` infra SSOT 文件前 | 停下 | 該 repo 不在本 session 原始 scope，需 §2.15 confirm |
| C4 | 憑證簽發完成、要請 Human 切 Cloudflare 橘雲前 | 停下 | 切換時機（切錯會短暫無法連線）|

## Acceptance

- [auto] the parser SHALL 從實際 HTML fixture 解出 `edition == "4.0"` 且 `publication_date == "2023-05-26"` — `pytest tests/test_iec.py`
- [auto] WHEN HTML 內不存在 `lifecycles` 區塊 THEN the parser SHALL 拋出可辨識的解析錯誤、SHALL NOT 回傳空結果 — `pytest tests/test_iec.py::test_missing_lifecycles_raises`
- [auto] WHEN HTML 內不存在 `underDevelopmentProduct` THEN the parser SHALL 正常回傳、`under_development` 為 `None` — `pytest tests/test_iec.py::test_missing_under_development_ok`
- [auto] WHEN 基準檔不存在 THEN `POST /api/check` SHALL 回傳 `status == "baseline_created"` — `pytest tests/test_api.py`
- [auto] WHEN 本次資料與基準相同 THEN `POST /api/check` SHALL 回傳 `status == "no_update"` — `pytest tests/test_api.py`
- [auto] WHEN 本次資料與基準不同 THEN `POST /api/check` SHALL 回傳 `status == "updated"` 且 `changes` 非空、每筆含 `before` / `after` — `pytest tests/test_api.py`
- [auto] WHEN 抓取或解析失敗 THEN `POST /api/check` SHALL 回傳 `status == "error"` 且基準檔內容 SHALL 不變 — `pytest tests/test_api.py::test_error_does_not_overwrite_baseline`
- [auto] the app SHALL NOT 引用任何外部 CDN 資源 — `grep -rE "https?://(cdn|unpkg|jsdelivr|fonts\.googleapis)" app/ | wc -l` 為 0
- [manual] 本機 `docker compose up` 後、容器 RSS SHALL < 100 MB — `docker stats --no-stream`
- [manual] VPS 上 `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:20080/healthz` SHALL 回 `200`
- [uat] Human 照 issue #1 `## UAT Checklist` 10 條於 `https://smalldick.etbiss.com` 逐條驗收

## Doc Sync Scope

**Must update**：
- `small_dick_crawler/aiREAD.md` — §3 專案結構（補 `app/` `tests/` 等）、§5 開發 loop（補安裝 / 跑 / 測三行）、§「執行環境」段（BASE 20000 投影 + 啟動命令）
- `small_dick_crawler/aiPJINDEX.md` — 頂層佈局補新目錄、功能模組由「無」改為實列
- `small_dick_crawler/CLAUDE.md` — 「未定：技術棧」段改為已定（Flask + gunicorn + Docker）

**Audit only**：
- `small_dick_crawler/README.md` — 一句話定位不變，確認無需改
- `ett-et/etchai` `docs/` — 加一份 conf.d 檔是否需在其 deploy 文件提及（預期否，因該 repo 文件未逐一列舉租戶）

**Out of scope** / **Do not touch**：
- `~/projects/project_maker/standards/*` — port BASE 登錄由 `project_maker#375` 處理，本 plan 不動
- `ett-et/lifetool` / `ett-et/ymes` — 既有 conf 未進版控由 `lifetool#10` / `ymes#218` 各自處理
- `od_vps_...` infra SSOT — **需同步但不在本 session scope**，於 C3 停下取得 §2.15 confirm 後再動

## 變更記錄

- 2026-09-04：建立 plan，寫入 D1–D7（來源：與 Human 的需求收斂對話 + 本 session 對目標站點與部署環境的實查）
