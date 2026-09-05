# small_dick_crawler Observability Map

> 地圖 = **現況投影**，⛔ 不是 SSOT。本檔記「現在查得到什麼」，⛔ 不主張「應該要有什麼」。
> **⚠️ 誠實界定：本 repo 幾乎沒有可觀測性。** 這張圖存在的價值主要是把**盲區**寫清楚。

## 現在有的

| 手段 | 內容 | 出處 |
|---|---|---|
| `GET /healthz` | 純文字 `ok` / 200，⛔ 不檢查磁碟、不檢查對外連線 —— 只證明「程序活著」| `app/main.py:52-54` |
| gunicorn access log | 打到 stdout（`--access-logfile -`），可用 `docker logs smalldick_web` 看 | `Dockerfile:21-22`、`docker-compose.yml:19` |
| 資源用量 | `docker stats`（部署時實測常駐 42 MB / CPU 0.06%）| issue #1 部署 comment |
| `last_check.json` | 上一次**成功比對**的時間 / 結果 / 變動欄位數，同時顯示在頁面上 | `app/main.py:195-202`、`app/templates/index.html:98-104` |

## ⛔ 沒有的

- **無 app 層 logging** —— 全 `app/` grep 不到 `logging` / `logger` / `print`。
- 無 metric、無 alert、無 audit trail、無錯誤追蹤（Sentry 之類）、無 uptime 監測。
- 無結構化 log、無 request id。

## ⚠️ 主要盲區（現況，非待辦）

1. **解析失敗只有按按鈕的人看得到。** IEC 改版導致 `ParseError` 時，錯誤只出現在那一次的 HTTP 回應裡（`app/main.py:116-122`）；伺服器端不留任何紀錄，`last_check.json` 也不寫（失敗路徑在寫入之前就 return）→ **沒人按按鈕就沒人知道工具已經壞了**。access log 只會顯示一筆 200（錯誤是以 200 + `status=error` 回傳的，`app/main.py:101`）。
2. **HTTP 狀態碼分辨不出成敗** —— 所有結果（含 `error`）都回 200，故從 access log／外部監測看不出失敗率。
3. **`last_check.json` 不記錄失敗** —— 檔內的「上次檢查」實為「上次**成功比對**」，中間失敗過幾次無從得知。
4. **重新部署有數秒 502 空窗** —— `up -d --build` 會重建容器，實測期間外部曾打到一次 502（issue #1 部署 comment「已知運維事項 1」）。無 health-check gate、無 graceful 切換。

## 出問題時怎麼查（現況可行的順序）

```
1. curl https://smalldick.etbiss.com/healthz            → 200？（程序活著嗎）
2. curl http://172.17.0.1:2000/healthz                  （在 VPS host 上，跳過 nginx）
3. docker exec etchai_nginx wget -qO- \
     http://172.17.0.1:2000/healthz                     （nginx 容器連得到嗎）
4. docker logs --tail 100 smalldick_web                 （只有 access log，⛔ 無應用錯誤）
5. 直接開頁面按一次「檢查版本」                            ← ⚠️ 目前唯一能看到解析錯誤訊息的方法
```

（步驟 1→5 = 由便宜到貴。第 5 步之所以排最後卻不可省，正是因為盲區 1。）
