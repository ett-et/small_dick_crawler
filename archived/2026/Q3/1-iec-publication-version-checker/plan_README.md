---
slug: iec-publication-version-checker
title: IEC 標準版本檢查工具 — smalldick.etbiss.com 單頁 check new
created: 2026-09-04
type: LocalPlan
upstream: issue #1
branch: feat/1-iec-publication-version-checker
shipped: true
dev_merged: true
---

# IEC 標準版本檢查工具

## Tracking

Issue: https://github.com/ett-et/small_dick_crawler/issues/1

## Goal

在 `smalldick.etbiss.com` 上線一個單頁工具：一個「check new」按鈕，按下去比對 IEC publication 85813（IEC 62368-1:2023 RLV）的版本資料是否與上次記錄不同，結果顯示在頁面下方。

需求 SSOT = issue #1（本 plan 不重抄需求，只定**怎麼做**）。

## Context

**目標站點事實** → **見 issue #1 `## Technical Constraints`**（需求 SSOT，本 plan 不重抄；per L22）。

本 plan 只留**設計級**的 grounding —— 亦即會直接決定 D1–D7 怎麼寫的那幾條：

- 版本資料是 Alpine `x-data` 工廠函式 return 字面量內的 **JS 物件字面量**（`lifecycles: {...}` / `underDevelopmentProduct: {...}`），**不是** DOM 節點、**不是** ld+json → 決定了 D2 用 brace-matching 而非 HTML parser。
- **服務端 HTML 內不存在 `<script type="application/ld+json">` 元素**；`application/ld+json` 該字串只在 JS 內出現一次（`script.type = 'application/ld+json'`，前端動態注入 breadcrumb 用）→ 不可作資料來源。
  > ⚠️ 本條**更正**了 issue #1 `## Technical Constraints` 的「ld+json 存在但為空」—— 該敘述不實（結論不變、事實錯）。已於 issue #1 貼更正 comment。

**部署環境現況**：

| 項目 | 值 | 來源 |
|---|---|---|
| VPS | DigitalOcean SGP1、`157.230.34.164`、Ubuntu 24.04、**1 vCPU / 2 GB RAM** | `od_vps_ubuntu-s-1vcpu-2gb-70gb-intel-sgp1-01/README.md` |
| 既有租戶 | `etchai.etbiss.com` / `lifetool.etbiss.com` / `ymetc.com`（同一台、同一組 nginx） | 同上 `docs/network.md` |
| 反向代理 | 容器 `etchai_nginx`（`nginx:alpine`），conf 於 `/opt/etchai/nginx/conf.d/` | `etchai/docker-compose.prod.yml:146-163` |
| conf 掛載 | `- ./nginx/conf.d:/etc/nginx/conf.d:ro`（**整目錄** bind-mount） | `etchai/docker-compose.prod.yml:155` |
| TLS | certbot 容器 + **host bind-mount**（`./certbot/conf:/etc/letsencrypt`、`./certbot/www:/var/www/certbot`）→ 憑證實體落 `/opt/etchai/certbot/conf/live/<domain>/`；⛔ **不是 named volume** | `etchai/docker-compose.prod.yml:158-159,170-171` |
| etchai repo 追蹤的 conf | 只有 `nginx/nginx.conf`、`conf.d/default.conf`、`conf.d/etchai.conf` | `git -C ~/projects/etchai ls-files nginx` |
| **conf 的實際慣例** | **各服務放自己 repo 的 `deploy/nginx/`，部署時複製到 conf.d** | `git -C ~/projects/lifetool ls-files` → `deploy/nginx/lifetool{,-temp}.conf` |
| nginx 容器網路 | `etchai_nginx` 只接 `etchai_etchai_network`（`172.19.0.7`），**不在 default bridge** | VPS `docker inspect etchai_nginx` |
| upstream 慣例（兩種先例） | `lifetool_web` 走**容器名**（同網路、零 published port）／ `ymes-channel-gateway` 走 **`172.17.0.1:8004`**（publish 在 `0.0.0.0`） | VPS `docker ps` + `/opt/lifetool/docker-compose.prod.yml` + `od_vps_.../docs/network.md` |
| **實測（本 session 拋棄式探針）** | 容器 publish 在 `172.17.0.1:<port>` 時：`etchai_nginx` 容器內**連得到** ✅／host 連得到 ✅／**公網 IP 連不到** ✅（`http=000`） | VPS `docker run --rm -p 172.17.0.1:20080:80` + `docker exec etchai_nginx wget`，測完即移除（探針用 20080、結論與實際採用的 2000 同理，皆為 `172.17.0.1` 綁定）|
| DNS | Cloudflare；`smalldick` A → `157.230.34.164` 已由 Human 於 2026-09-04 新增（暫「僅限 DNS」） | Human 回報 + `dig` |

**前置依賴**：port BASE **21000** 登錄追蹤於 `ett-et/project_maker#375`（Human 於 2026-09-04 指定用 21000、非表上佔位的 20000）。#375 未落地前先借用該段、不與他人衝突（VPS 與本機皆實查 21000 段空）。

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
  - ld+json（拒絕：服務端 HTML 內根本沒有該元素，見 `## Context`）
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

- 規則：後端記住上次實際抓取的時間，10 秒內的重複請求**不對 IEC 發新請求**，直接回上次結果。
- **⛔ 節流不是第五種 status**：回應的 `status` 恆為既有四值之一（`baseline_created` / `no_update` / `updated` / `error`，= 上次那一次的結果），另帶布林旗標 `throttled: true` 表示「這是快取、沒有真的去抓」。issue #1 `## Acceptance`「結果 SHALL 明確落在四者之一」因此仍成立。前端在請求進行中停用按鈕。
- 理由：滿足 issue #1「不得對目標站點高頻打點」與 repo 紅線。單 worker → 程序內狀態即足夠。
- 替代方案：Redis / 檔案鎖（拒絕：單 worker 單機，過度設計）

### D6 — nginx 設定檔放**本 repo** `deploy/nginx/`，⛔ 不動 `ett-et/etchai`

> **v2（2026-09-04 修正）** —— 原 D6 規定「以 PR 進 `ett-et/etchai` 的 `nginx/conf.d/`」，是基於「conf 一定放 etchai repo」的**錯誤推論**。實查 lifetool 後推翻，見下方理由與 `## 變更記錄`。

- 規則：`smalldick.conf` + `smalldick-temp.conf` 放**本 repo** `deploy/nginx/`；部署時 `scp` 複製到 VPS `/opt/etchai/nginx/conf.d/`。**本工作不需要動 `ett-et/etchai` 任何檔案。**
- 理由 —— 這是**既有慣例**，不是新發明（實查 2026-09-04）：
  - `git -C ~/projects/lifetool ls-files` → `deploy/nginx/lifetool.conf` + `deploy/nginx/lifetool-temp.conf`
  - VPS 上 `/opt/etchai/nginx/conf.d/lifetool.conf` 檔頭自述：「部署位置：複製到 VPS `/opt/etchai/nginx/conf.d/lifetool.conf`（`etchai_nginx` 掛載此目錄）」+「首次簽證 chicken-egg…先用 `lifetool-temp.conf`（僅 HTTP + ACME challenge）簽完 cert 再放本檔 + reload」
  - → conf 跟著**服務自己的 repo** 走、故障域不綁一起、etchai 不必替所有租戶背設定
- **雙檔 pattern 必須照抄**：`smalldick-temp.conf`（只有 :80 + ACME challenge）供首次簽證用；`smalldick.conf`（含 :443）在 cert 簽發後才放上去。**先放含 443 的版本會讓 nginx reload 失敗**（引用不存在的 cert 檔）→ 連帶影響同一個 nginx 的其他三個租戶。
- 替代方案：
  - 進 `ett-et/etchai` repo（**拒絕**：與既有慣例相反、把故障域綁在一起、且需跨 repo PR）
  - 直接在 VPS 手寫不進版控（拒絕：無留底，且慣例本就有留底處）
- **續簽保險（per review r1 #5）**：`smalldick.conf` 的 **:443 block 也放一份** `location /.well-known/acme-challenge/ { root /var/www/certbot; }`。理由：`etchai.conf` 的 :443 block 沒放，一旦 Cloudflare zone 開了 Always Use HTTPS，:80 的 challenge 會被 CF 301 到 https 而落進 app → 12h renew loop **靜默失敗**。成本近零的保險。
- **既有債（不在本 plan 修）**：`etchai/docker-compose.prod.yml:172` 註明「renew 後需手動 restart nginx」→ 憑證續簽後不會自動生效。屬 etchai 既有狀況，本 plan 只記錄、不處理。
- **對既有授權的影響**：Human 於 2026-09-04 授權「可以動 etchai nginx」—— 本修正後**用不到該授權**，範圍反而縮小。

### D7 — 容器 publish 在 `172.17.0.1:2000`，nginx 以 **IP 字面值** 反代

> **v3.1（2026-09-04，Human 指定 port）** —— v3 用 20080，Human 改指定 **2000**；⛔ 綁定位址與 IP 字面值的**理由與結論一字未變**、只換數字。
>
> **v3（2026-09-04，經 VPS 實測拍板）** —— v1 寫 `127.0.0.1:20080`（**連不通**）、v2 改 join `etchai_etchai_network` 走容器名（**引入更嚴重的問題**，見下）。v3 為最終規則。

- 規則：本服務用**自己的** `docker-compose.prod.yml`，容器名 `smalldick_web`，publish **`- "172.17.0.1:2000:8000"`**；nginx 以 `proxy_pass http://172.17.0.1:2000` 反代（**IP 字面值、不用 hostname**）。
- **v3 實測證據**（VPS 上起拋棄式 `nginx:alpine` 探針 publish 在 `172.17.0.1:20080`，測完即 `docker rm -f`）：

  | 從哪裡連 | 結果 |
  |---|---|
  | `docker exec etchai_nginx wget http://172.17.0.1:<port>/` | ✅ 連得到 |
  | host `curl http://172.17.0.1:<port>/` | ✅ `http=200` |
  | **公網** `curl http://157.230.34.164:<port>/` | ✅ **連不到**（`http=000`）→ 未暴露 |

- **為什麼不用 v2 的容器名（這是關鍵）**：nginx 對 `upstream`/`proxy_pass` 內的**字面 hostname 在 config parse 時就解析**。若 `smalldick_web` 沒在跑，`etchai_nginx` 會以 `host not found in upstream` **啟動失敗** → **連帶弄掛 etchai / lifetool / ymetc 三個租戶**。這直接違反 issue #1 `## Non-functional`「本工具故障不得影響同機其他服務」。
  - `lifetool.conf` 確實用容器名（既有慣例），但那是**既有的隱性耦合**，不是本服務該照抄的部分 —— 慣例照抄「conf 放自己 repo」（D6）✅，**不照抄「用容器名」** ❌。
  - 走容器名又要免耦合，需 `resolver 127.0.0.11 valid=10s;` + 變數式 `proxy_pass $upstream;`（延遲到 request 時才解析）—— 可行但更複雜，且 IP 字面值已同時滿足所有需求。
- **IP 字面值的代價（誠實界定）**：`172.17.0.1` 是 docker0 的 gateway 位址，**理論上**可能因 docker 網段設定改變而變動（實務上極穩定，且 `ymetc.com` 已用同一位址跑了數月）。若真變動 → nginx 502，症狀明確、易查；已列入 `## Acceptance` 的健康檢查項。
- **與 `Port:` line 的關係**：`Port: 21001`（issue #1 = BASE 21000 + issue#1）是**驗收者本機**跑起來自測用的 port（per `issue_backlog_workflow.md` R2）；`2000` 是 **VPS 上的 publish port**。兩者不同機、不同層、不衝突 —— VPS publish port **不需要**落在該 repo 的 BASE 段內。
- **`2000` 是 IANA registered port（cisco-sccp）**：因為只綁 `172.17.0.1`、不綁 `0.0.0.0`，公網掃不到、也不與該主機上任何服務衝突（VPS `ss -tlnp` 實查 2000 / 21000 皆空）。
- 替代方案：
  - publish `127.0.0.1:2000`（**拒絕：實測連不通** —— DNAT 只裝 dst=127.0.0.1，容器封包永遠落不到 loopback）
  - publish `0.0.0.0:2000`（`ymetc` 先例）（拒絕：docker publish 繞過 UFW → 直接對公網敞開）
  - join `etchai_etchai_network` + 容器名（**拒絕：會讓本服務的故障擴散成全站故障**，見上）
  - 塞進 etchai 的 compose（拒絕：故障域綁一起）

### D8 — 兩顆按鈕：「檢查版本」只讀、「建立／更新基準」才寫

> **新增（2026-09-04，Human 指示）** —— 原設計是**一顆**按鈕：第一次按建立基準、之後每次按都比對**並順手覆寫基準**。Human 要求拆成兩顆。

- 規則：
  - **`POST /api/baseline`（建立／更新基準）** —— 抓一次、把現況寫成新基準。status `baseline_set`。
  - **`POST /api/check`（檢查版本）** —— 抓一次、與基準比對，**⛔ 任何情況都不寫基準**；只寫 `last_check.json`（時間 + 結果）。status `no_update` / `updated`。
  - 沒有基準時按檢查 → status **`no_baseline`**，前端該按鈕同時 disabled。
- **為什麼這不只是 UI 拆分（實質行為改善）**：單顆按鈕時，偵測到「有更新」之後再按一次就會變成「沒有更新」—— 因為上一次比對已經把基準覆寫掉了，**等於工具自己把警訊抹掉**。拆開後，更新訊號會**一直留著**，直到人按下「更新基準」明示確認（= 「我知道了」）。
- **status 由 4 值變 5 值**：`baseline_set` / `no_baseline` / `no_update` / `updated` / `error`。issue #1 `## Acceptance` 原寫「四者之一」，已隨本變更同步更新（需求 SSOT 先改、per `issue_backlog_workflow.md` R2 (D) churn guard）。
- **節流改為 per-action**：兩個動作各自計時（按了檢查不該把更新基準也鎖住）。
- **⛔ 節流只快取「真的抓過 IEC」的結果**：`no_baseline` 沒有發出任何外部請求 → 不進快取。**本機實測踩到**：建立基準後再按檢查，仍回被快取的 `no_baseline`；已修並補回歸測試。
- 替代方案：
  - 維持單顆按鈕（**拒絕**：Human 明示要拆；且單顆會抹掉更新訊號）
  - 檢查時仍更新基準的 `checked_at`（拒絕：那還是在寫基準檔，破壞「檢查只讀」的單純語意；改用獨立的 `last_check.json`）

### D9 — 差異表逐項攤開，⛔ 不直接印 JSON

- 規則：`under_development` 與 `lifecycle_entries` 這兩個結構化欄位在差異表中 MUST 攤成「子項目」逐列顯示（`開發中版本｜階段  CD → PCC`、`版次歷史｜新增版次 …`），⛔ 不把整包物件 `JSON.stringify` 印出來。
- 理由：Human 於 2026-09-04 看畫面時指出整包 JSON 難讀。攤開後讀者一眼看得出「實際變的是哪一項」。
- 替代方案：印整包 JSON（拒絕：讀者要自己 diff 兩坨 JSON）／只顯示欄位名不顯示前後值（拒絕：失去「變成什麼」這個最重要的資訊）

## Approach

1. **專案骨架**（worktree 內）：`app/`（Flask app + 解析模組 + 模板）、`tests/`、`deploy/nginx/`（per D6）、`Dockerfile`、`.dockerignore`、`docker-compose.yml`（本機）+ `docker-compose.prod.yml`（VPS，per D7 v3）、`requirements.txt` + `requirements-dev.txt`。
2. **解析模組** `app/iec.py`：`fetch_html(url)` / `extract_blocks(html)` / `normalize(blocks)` / `diff(baseline, current)`。純函式、不碰網路的部分可離線測。
3. **儲存模組** `app/store.py`：`read_baseline()` / `write_baseline()` / `read_last_check()` / `write_last_check()`，全走同一支 atomic writer（per D8 兩個檔分開存）。
4. **Flask app** `app/main.py`：`GET /` 回頁面（含目前基準面板 + 上次檢查）、`POST /api/baseline`、`POST /api/check`、`GET /healthz`（per D8 兩個動作各自 endpoint、各自節流）。
5. **前端** `app/templates/index.html`：目前基準面板 + 兩顆按鈕 + 可收合的「怎麼判斷有更新」說明 + 結果區塊（差異表逐項攤開，per D9）；無外部 CDN（自帶樣式）。
6. **測試**：用**存下來的真實 HTML fixture** 測解析與比對；不在測試中連外網。
7. **本機驗證**：起容器、按按鈕走完四種結果（已建立基準 / 沒有更新 / 有更新 / 檢查失敗）。
8. **部署**：VPS `git clone` 到 `/opt/small_dick_crawler` → `docker compose -f docker-compose.prod.yml up -d --build` → 兩處確認健康：host `curl http://172.17.0.1:2000/healthz` **且** `docker exec etchai_nginx wget -qO- http://172.17.0.1:2000/healthz`（後者才證明 nginx 連得到，per review r1 #2）。
9. **nginx + 憑證**：本 repo 寫 `deploy/nginx/smalldick-temp.conf`（僅 :80 + ACME）與 `deploy/nginx/smalldick.conf`（:80 轉址 + :443，**兩個 block 都含 acme-challenge location**）→ `scp` temp 版到 `/opt/etchai/nginx/conf.d/` → `docker exec etchai_nginx nginx -t && nginx -s reload` → 於 `/opt/etchai` 跑 `docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d smalldick.etbiss.com`（憑證落 `/opt/etchai/certbot/conf/live/smalldick.etbiss.com/`）→ 換上正式版 → `nginx -t` → reload。
10. **收尾**：更新 `aiREAD.md`（執行環境段）+ `aiPJINDEX.md`；`od_vps_.../docs/{services,network}.md` 需同步（跨 repo，於 C3 停下取得授權或開票）。

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
| C1 | 本機跑起來、畫面可看 | 停下，把畫面截圖 / 文案貼給 Human | **畫面與文案定稿**（純美感 / 用語判斷，測試驗不了）|
| C2 | 要 reload 生產 nginx 前（共用給另外三個租戶）| 停下 | **這一次動手的時機**（reload 失敗會同時弄掛 etchai / lifetool / ymetc；授權已有、要 confirm 的是時間點）|
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
- [auto] WHEN 10 秒內重複 `POST /api/check` THEN the system SHALL NOT 對外發出新請求、且回應 SHALL 帶 `throttled == true` 而 `status` 仍為四值之一 — `pytest tests/test_api.py::test_throttle`
- [manual] VPS host 上 `curl -s -o /dev/null -w '%{http_code}' http://172.17.0.1:2000/healthz` SHALL 回 `200`
- [manual] **the nginx container SHALL 連得到 upstream** — `docker exec etchai_nginx wget -qO- http://172.17.0.1:2000/healthz`（⛔ 只驗 host 側會漏掉「nginx 連不到」這個最可能的失敗，per review r1 #2）
- [manual] the service SHALL NOT 對公網暴露 2000 — `curl -m 5 -o /dev/null -w '%{http_code}' http://157.230.34.164:2000/` 回 `000`
- [manual] WHEN 憑證簽發完成 THEN `https://smalldick.etbiss.com/healthz` SHALL 回 `200` 且憑證有效 — `curl -sI https://smalldick.etbiss.com/healthz`
- [manual] the nginx config SHALL 通過語法檢查（保護另外三個租戶）— `docker exec etchai_nginx nginx -t`
- [uat] Human 照 issue #1 `## UAT Checklist` 10 條於 `https://smalldick.etbiss.com` 逐條驗收

## Doc Sync Scope

**Must update**：
- `small_dick_crawler/aiREAD.md` — §3 專案結構（補 `app/` `tests/` 等）、§5 開發 loop（補安裝 / 跑 / 測三行）、§「執行環境」段（BASE 20000 投影 + 啟動命令）
- `small_dick_crawler/aiPJINDEX.md` — 頂層佈局補新目錄、功能模組由「無」改為實列
- `small_dick_crawler/CLAUDE.md` — 「未定：技術棧」段改為已定（Flask + gunicorn + Docker）

**Audit only**：
- `small_dick_crawler/README.md` — 一句話定位不變，確認無需改
- `ett-et/etchai` `docs/` — **本 plan 不動 etchai repo 任何檔案**（per D6 v2）；但 conf 會 scp 進**該 VPS 的** `/opt/etchai/nginx/conf.d/` → audit「是否需在其 deploy 文件提一句多了一個租戶」（預期否，該 repo 文件未逐一列舉租戶）

**Out of scope** / **Do not touch**：
- `~/projects/project_maker/standards/*` — port BASE 登錄由 `project_maker#375` 處理，本 plan 不動
- `ett-et/lifetool` / `ett-et/ymes` — 既有 conf 未進版控由 `lifetool#10` / `ymes#218` 各自處理
- `od_vps_...` infra SSOT — **需同步但不在本 session scope**，於 C3 停下取得 §2.15 confirm 後再動

## 變更記錄

- 2026-09-04：建立 plan，寫入 D1–D7（來源：與 Human 的需求收斂對話 + 本 session 對目標站點與部署環境的實查）
- 2026-09-04：**推翻 D6 原規則**（原：conf 以 PR 進 `ett-et/etchai`）→ 改為放本 repo `deploy/nginx/`、不動 etchai。原規則基於「conf 一定放 etchai repo」的錯誤推論；實查 `git -C ~/projects/lifetool ls-files` 發現既有慣例是「各服務放自己 repo」。（來源：VPS 唯讀實查 + lifetool repo 實查）
- 2026-09-04：**推翻 D7 原規則**（原：publish `127.0.0.1:20080` + `proxy_pass 172.17.0.1:20080`）→ 改為 join `etchai_etchai_network`、`expose` 不 publish、走容器名。原規則**實際連不通**：`docker inspect etchai_nginx` 顯示 nginx 只在 `etchai_etchai_network`（172.19.x），而 bind 在 host loopback 的 port 容器連不到。（來源：VPS `docker inspect` / `docker ps` 實查）
- 2026-09-04 [struct]：D6 / D7 各加一段 v2 修正註記，section 結構未變（core 8 齊、順序未動）
- 2026-09-04：**D7 再推翻一次 → v3**（v2 的「join 共用網路走容器名」改為「publish `172.17.0.1:20080` + IP 字面值 proxy_pass」）。理由：nginx 對字面 hostname 在 **config parse 時**解析，本容器沒起會讓 `etchai_nginx` 啟動失敗、**連帶弄掛另外三個租戶** —— 直接違反 issue #1 `## Non-functional`。VPS 拋棄式探針實測 `172.17.0.1:20080` 三面皆符合預期（nginx 容器連得到 / host 連得到 / 公網連不到）。（來源：plan self-review r1 finding #1 + 本 session VPS 實測）
- 2026-09-04：修正 `## Context` 兩處不實 cite —— ld+json「存在但為空」→ 實為**服務端 HTML 內不存在該元素**；certbot「`/etc/letsencrypt` volume」→ 實為 **host bind-mount** `./certbot/conf`。issue #1 同句錯誤已另貼更正 comment。（來源：self-review r1 finding #3 / #4）
- 2026-09-04：`## Context` 目標站點段收斂為 pointer 回 issue #1，只留設計級 grounding（消除與需求 SSOT 的雙寫）。（來源：self-review r1 finding #6）
- 2026-09-04：D6 補「:443 block 也放 acme-challenge location」續簽保險 + 記錄 etchai「renew 後需手動 restart nginx」既有債。（來源：self-review r1 finding #5）
- 2026-09-04：D5 明示節流**不是第五種 status**、改用 `throttled` 旗標，並補一條 `[auto]` acceptance。（來源：self-review r1 finding #8）
- 2026-09-04：`## Acceptance` 補 6 條（nginx 容器端可達性 / 公網未暴露 / https 端到端 / `nginx -t` / 節流 / host 健康檢查），補上原本驗不到 D7 失效的盲區。（來源：self-review r1 finding #2）
- 2026-09-04 [struct]：C1 / C2 改寫為真正的未知分岔（原 C1 是 progress milestone、C2 的授權已拍板）。（來源：self-review r1 finding #7）
- 2026-09-04：Approach step 1 補列 `deploy/nginx/` 與 `docker-compose.prod.yml`；`## Doc Sync Scope` 的 etchai audit 條改寫（D6 v2 後不動 etchai repo，但 conf 仍會 scp 進該 VPS 目錄）。（來源：self-review r2 觀察 2 / 3）
- 2026-09-04：**port 兩處改號（Human 指定）** —— (a) 本 repo BASE 由表上佔位的 20000 改為 **21000**（feat port 隨之 20001 → **21001**）；(b) VPS docker publish port 由 20080 改為 **2000**。⛔ D7 的**綁定位址（`172.17.0.1`）與 IP 字面值 proxy_pass 的理由與結論一字未變**，只換數字。VPS `ss -tlnp` + 本機 `lsof` 實查 2000 / 21000 / 21001 皆空。`project_maker#375` 需同步改登錄值。（來源：Human 指示 2026-09-04）
- 2026-09-04：**新增 D8**（兩顆按鈕：檢查只讀、建立／更新基準才寫）+ **D9**（差異表逐項攤開、不印 JSON）。D8 不只是 UI 拆分 —— 單顆按鈕會在偵測到更新後把基準覆寫掉、**自己抹掉警訊**；拆開後更新訊號留到人明示確認為止。status 由 4 值變 5 值、節流改 per-action。（來源：Human 指示 2026-09-04 + 看畫面回饋）
- 2026-09-04：修節流快取 bug —— `no_baseline` 沒發出外部請求卻被快取，導致「建立基準後再按檢查仍回 no_baseline」。改為只快取真的抓過的結果，並補回歸測試。（來源：本機實測）
- 2026-09-04：**shipped** —— Human 於 `https://smalldick.etbiss.com` UAT pass 並明示授權 close。（來源：Human 2026-09-04）
