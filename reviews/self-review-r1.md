---
classification: env
verdict: REQUEST_CHANGES
round: 1
reviewer: independent sub-reviewer (general-purpose agent)
date: 2026-09-04
target: active/1-iec-publication-version-checker/plan_README.md
---

# plan self-review r1

> per `issue_backlog_workflow.md` R7 v1.9 — issue-ok 自主窗口內的 bounded auto-loop，substrate = 本 sidecar；3-strike 計數依 frontmatter `classification`（本輪 = `env`）。

## Lens A — 內部一致性

| # | 檢查 | 結果 |
|---|---|---|
| 1 | core 8 sections + canonical 順序 | ✅ 齊、順序符合 `shared_plan_schema.md:259-273`；`## Steps`（infra_run 專屬）/ `## Dependencies`（frontmatter 無 `depends_on`）正確省略 |
| 2 | Acceptance tag + 可驗命令 + EARS-lite | ✅ 11 條全帶 tag 與驗證命令；event-driven 用 `WHEN…THEN…SHALL`、invariant 用 ubiquitous。**但覆蓋面有洞** → finding #2 / #8 |
| 3 | Test Strategy 4 行格式 | ✅ |
| 4 | Checkpoints 是否為真「未知分岔」 | ⚠️ C3 / C4 是真分岔；C1 是 progress milestone、C2 的授權已拍板 → finding #7 |
| 5 | Decisions vs issue 矛盾 / 雙寫 | ⚠️ 無矛盾（timeout 30s / <100MB / atomic / volume / on-demand 全對得上）；但 `## Context` 與 issue `## Technical Constraints` 雙寫 → finding #6；D5「節流中」不在四 status 內 → finding #8 |
| 6 | frontmatter v1-light | ✅ 八欄對齊 `shared_plan_schema.md:219-231`；未寫已 deprecate 的 `status`；slug 與 issue body 一致 |

## Lens B — 環境 grounding（逐條複驗）

**目標站點**（reviewer 實跑 curl 複驗）

| cite | 結果 |
|---|---|
| `200 494055` + 0.4s | ✅ bytes 完全一致 |
| `robots.txt` → 200 / size 0 | ✅ |
| `lifecycles` / `underDevelopmentProduct` 內嵌於 Alpine `x-data` return 字面量 | ✅（offset 264383 / 264165）；`"edition":"4.0"` / `"publication_date":"2023-05-26"` 實際存在 |
| 「單次 GET 即可、不需 headless」 | ✅ 結論成立 |
| **「ld+json 存在但內容為空」** | ❌ **不符** — 服務端 HTML **完全沒有**該元素；字串只在 JS 內出現一次（前端動態注入 breadcrumb）→ finding #3 |

**部署環境**

| cite | 結果 |
|---|---|
| VPS 規格 / SGP1 / 1vCPU 2GB | ✅ |
| 三租戶 | ✅ |
| `docker-compose.prod.yml:146-163` nginx block | ✅ 行號精確 |
| `:155` conf.d 整目錄 bind-mount | ✅ 行號精確 |
| `etchai.conf:11-13` ACME challenge | ✅ 行號精確 |
| **「certbot + `/etc/letsencrypt` volume」** | ❌ **不符（輕微）** — 實為 host bind-mount `./certbot/conf`（`:158` ro / `:170` rw）+ `./certbot/www`（`:159` / `:171`）；憑證落 `/opt/etchai/certbot/conf/` → finding #4 |
| etchai repo 只追蹤 3 份 conf | ✅ `git ls-files nginx` 實跑一致 |
| `smalldick` A 記錄 + 灰雲 | ✅ `dig` → `157.230.34.164`（對照 etchai → CF anycast = 橘雲）|
| port BASE 20000 未登錄 / 追蹤 #375 | ✅ `issue_backlog_workflow.md:212` +（`gh issue view 375` OPEN / `backlog`）|

**設計面風險**

| 項目 | 結果 |
|---|---|
| `172.17.0.1` host gateway 在該 VPS 可用 | ✅（`ymetc.com → 172.17.0.1:8004` live「Up 4 months」）|
| **`127.0.0.1:20080` 綁法與該先例同構？** | ❌ **不同構** → finding #1（阻擋級）。先例是 `- "8004:8004"`（綁 0.0.0.0）|
| Cloudflare 橘雲 vs HTTP-01 先後 | ✅ 順序正確；**但續簽**有殘餘風險 → finding #5 |
| 基準檔 volume 寫法 | ✅ 同 filesystem `os.replace()` 原子；`up -d` 重建不掉（僅 `down -v` 會清，屬正常語意）|

## Findings 與處置

| # | 嚴重度 | 分類 | 問題（摘要） | 處置 |
|---|---|---|---|---|
| 1 | **高（阻擋）** | env | `127.0.0.1:20080` publish 與 `proxy_pass 172.17.0.1:20080` 互斥 → 部署必 502。DNAT 只裝 dst=127.0.0.1，容器封包落不到 loopback | ✅ **採納，但不照建議的兩個選項**。改 **D7 v3 = publish `172.17.0.1:20080`**（reviewer 首選）。⚠️ 同時**採納 reviewer 對 v2 的警告**（join 共用網路 + 容器名 → nginx parse 時解析 hostname → 本容器沒起會讓 `etchai_nginx` 啟動失敗、弄掛三個租戶）。**已於 VPS 起拋棄式探針實測**：nginx 容器連得到 ✅ / host 連得到 ✅ / 公網連不到 ✅ |
| 2 | 中 | env | Acceptance 剛好驗不到 #1（只驗 host 側 `127.0.0.1` 會照樣 200）；無端到端 https 驗證 | ✅ **採納**。Acceptance 補 6 條：nginx 容器端可達性 / 公網未暴露 / https 端到端 / `nginx -t` / 節流 / host 健康檢查 |
| 3 | 低 | env | `## Context` 的 ld+json 敘述不實 | ✅ **採納**。Context 改寫；D2 替代方案理由同步修；**issue #1 同句已另貼更正 comment** |
| 4 | 低 | env | certbot 是 bind-mount 不是 volume；影響簽發命令落點 | ✅ **採納**。Context 表修正；Approach step 9 補具體 `certonly --webroot` 命令與憑證落點 |
| 5 | 低 | env | :443 block 缺 acme-challenge → 切橘雲後若 CF 開 Always Use HTTPS，續簽會靜默失敗 | ✅ **採納**（成本近零的保險）。D6 明訂兩個 block 都放；另記錄 etchai「renew 後需手動 restart nginx」既有債（`compose:172`）、不在本 plan 修 |
| 6 | 低 | scope | `## Context` 與 issue `## Technical Constraints` 雙寫，與 plan L22 自相矛盾 | ✅ **採納**。Context 目標站點段收斂為 pointer，只留設計級 grounding |
| 7 | 低（nit） | struct | C1 是 progress milestone；C2 的授權已在 issue 拍板 | ✅ **採納**。C1 收斂為「畫面與文案定稿」；C2 改寫為「這一次 reload 的時機」 |
| 8 | 低（nit） | scope | 「節流中」是未列舉的第五種 status | ✅ **採納**。明示節流回傳既有四 status 之一 + `throttled: true` 旗標；補一條 `[auto]` |

**推翻 / 不照改**：無。8 條全數採納（per `behavioral_constraints.md §2.14` v1.1 §4「REQUEST_CHANGES 也可能是錯的」—— 本輪逐條 source-verify 後皆成立）。

**額外收穫（reviewer 未提、修 #1 時連帶發現）**：reviewer 對 v2 方案的警告本身比 finding #1 更重要 —— 它揭露既有 `lifetool.conf` 的容器名寫法帶有**隱性全站耦合**。本 plan 因此明訂「照抄慣例的 conf 落點（D6）✅、**不照抄容器名 upstream** ❌」。

## VERDICT: REQUEST_CHANGES

→ 已全數修正，進 r2。
