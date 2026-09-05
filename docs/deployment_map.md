# small_dick_crawler Deployment Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。canonical = `Dockerfile` / `docker-compose*.yml` / `deploy/nginx/*`。
> 決策**理由**的沿革在 `archived/2026/Q3/1-iec-publication-version-checker/plan_README.md` D1 / D3 / D6 / D7 —— 本檔 ⛔ 不重抄，只標「現在長怎樣 + 哪裡不能亂動」。

## 拓撲

```
                Cloudflare DNS（smalldick A → 157.230.34.164，⚠️ 部署時為「僅限 DNS」灰雲）
                        │
                        ▼
    VPS 157.230.34.164（DigitalOcean SGP1、Ubuntu 24.04、1 vCPU / 2 GB）
    ┌────────────────────────────────────────────────────────────┐
    │  容器 etchai_nginx（nginx:alpine）  ← ⚠️ 四個租戶共用這一個  │
    │    conf.d/  ← bind-mount /opt/etchai/nginx/conf.d/           │
    │      etchai.conf / lifetool.conf / ymetc / smalldick.conf    │
    │         │                                                    │
    │         │ proxy_pass http://172.17.0.1:2000（IP 字面值）      │
    │         ▼                                                    │
    │  容器 smalldick_web  publish 172.17.0.1:2000 → :8000         │
    │    gunicorn app.main:app --workers 1 --threads 2 --timeout 60│
    │    volume smalldick_data → /data（baseline.json 等）          │
    └────────────────────────────────────────────────────────────┘
    同機租戶：etchai.etbiss.com / lifetool.etbiss.com / ymetc.com
```

## 環境一覽

| | 本機 dev | VPS 正式 |
|---|---|---|
| 檔 | `docker-compose.yml` | `docker-compose.prod.yml` |
| 容器名 | `smalldick_dev` | `smalldick_web` |
| publish | `21001:8000`（對 host 全介面）| `172.17.0.1:2000:8000` |
| 程式碼 | bind-mount `./app:/srv/app` + `--reload` | 烘進 image（`COPY app ./app`）|
| 資料 | volume `smalldick_dev_data` | volume `smalldick_data` |
| 位置 | worktree | `/opt/small_dick_crawler`（由 Human 以 sudo 建立）|

⚠️ `docker-compose.yml` 用的是 **21001** = issue #1 的 **feat port**（BASE 21000 + 1），不是 dev port 21000（`aiREAD.md §5` 的分配規則）。repo 內唯一的本機 compose 檔固定綁在這個號上。

## 環境變數（全部有預設值，⛔ 無 secret、⛔ 無 .env）

| 變數 | 預設 | 作用 | 出處 |
|---|---|---|---|
| `SMALLDICK_DATA_DIR` | `/data`（Dockerfile 也設一次）| 兩個 JSON 檔的落點 | `app/store.py:20`、`app/main.py:44-46`、`Dockerfile:5` |
| `SMALLDICK_THROTTLE_SECONDS` | `10` | 同動作最小重發間隔 | `app/main.py:23` |

⛔ 無 feature flag、無 rollout 開關、無多環境設定檔。

## ⛔ 不要亂動的地方（每條都有事故成本）

| 現況 | ⛔ 不要改成 | 會發生什麼 |
|---|---|---|
| `ports: "172.17.0.1:2000:8000"`（`docker-compose.prod.yml:24`）| `127.0.0.1:…` | nginx **容器**連不到（DNAT 只裝 dst=127.0.0.1）—— 已實測連不通 |
| 同上 | `0.0.0.0:…` | docker publish 繞過 UFW → 直接對公網敞開 |
| nginx `server 172.17.0.1:2000;`（`deploy/nginx/smalldick.conf:14-16`）| 容器名 upstream | nginx 在 **config 載入時**解析字面 hostname；本容器沒起 → `etchai_nginx` **啟動失敗** → **連帶弄掛 etchai / lifetool / ymetc** |
| `--workers 1`（`Dockerfile:21-22`）| 多 worker | 節流狀態存在程序記憶體 → 各自為政，對 IEC 的請求量變 N 倍（⛔ code 內只有註解、沒有機制擋）|
| 首次簽證先放 `smalldick-temp.conf` | 直接放含 `:443` 的正式檔 | 引用不存在的憑證 → `nginx -t` 失敗 → reload 失敗 → 弄掛另外三個租戶 |

**紅線：reload 前一律先 `docker exec etchai_nginx nginx -t`**（那個 nginx 同時服務四個租戶）。

## 部署 / rollout

```bash
ssh etchai-vps
cd /opt/small_dick_crawler && git pull
docker compose -f docker-compose.prod.yml up -d --build
curl -s -o /dev/null -w '%{http_code}\n' http://172.17.0.1:2000/healthz   # host 側
docker exec etchai_nginx wget -qO- http://172.17.0.1:2000/healthz         # nginx 容器側（關鍵）
```

⚠️ 兩側都要驗 —— 只驗 host 側會漏掉「nginx 連不到」這個最可能的失敗。
⚠️ `up -d --build` **會重建容器 → 數秒 502 空窗**（實測確有）。無 blue-green、無 graceful 切換。

**rollback**：⛔ 無自動機制。現況做法 = `git checkout <舊 commit>` 後重跑同一行 build。資料在 named volume，⛔ 不隨重建消失。

## nginx / TLS 現況

- conf 版控留底在**本 repo** `deploy/nginx/`，部署時 `scp` 到 VPS `/opt/etchai/nginx/conf.d/`（慣例同 lifetool；⛔ **不進** `ett-et/etchai` repo）。
- 兩份檔：`smalldick-temp.conf`（僅 :80 + ACME，首次簽證用）→ 簽發後換 `smalldick.conf`（:80 轉址 + :443）。
- 憑證 = Let's Encrypt，由 **etchai 那組 certbot** 簽發，實體落 `/opt/etchai/certbot/conf/live/smalldick.etbiss.com/`（host bind-mount，⛔ 不是 named volume）。部署時有效期至 2026-12-03。
- `:443` block **也放一份** `/.well-known/acme-challenge/`（`deploy/nginx/smalldick.conf:50-52`）—— 防 Cloudflare「Always Use HTTPS」把 :80 challenge 301 走導致續簽靜默失敗。
- ⚠️ **繼承的既有債**：憑證續簽後需**手動 restart nginx**（certbot 容器無法 reload 別的容器）。屬 etchai 既有狀況，本 repo 沿用同一組 certbot 故一併繼承、⛔ 未修。

## 未同步的跨 repo 文件（現況缺口）

`od_vps_ubuntu-s-1vcpu-2gb-70gb-intel-sgp1-01` 的 `docs/services.md` + `docs/network.md` **尚未**新增 `smalldick.etbiss.com` 一列 —— 該 repo 不在 issue #1 session 的 scope（plan Checkpoint C3），⛔ 至今未動。
