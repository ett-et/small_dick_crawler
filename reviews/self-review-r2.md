---
classification: none
verdict: PASS
round: 2
reviewer: independent sub-reviewer (general-purpose agent)
date: 2026-09-04
target: active/1-iec-publication-version-checker/plan_README.md
---

# plan self-review r2（收斂輪）

## r1 findings 複核：**8/8 已修正，無「修得不對」**

| # | r1 問題 | 狀態 |
|---|---------|------|
| 1 | `127.0.0.1:20080` 與 `proxy_pass 172.17.0.1` 互斥（阻擋級） | 已修正（D7 v3，四處一致；採納方式與 r1 建議不同但已誠實揭露 + 有 VPS 探針三面實測撐著）|
| 2 | Acceptance 驗不到 #1、無端到端 https | 已修正（Acceptance 11 → 16 條）|
| 3 | ld+json 敘述不實 | 已修正（Context + D2 + issue #1 更正 comment 三處同步）|
| 4 | certbot 是 bind-mount 不是 volume | 已修正（行號逐一複驗全中）|
| 5 | :443 缺 acme-challenge → 續簽靜默失敗 | 已修正（D6 + Approach step 9）|
| 6 | Context 與 issue 雙寫 | 已修正（收斂為 pointer）|
| 7 | C1/C2 不是真未知分岔 | 已修正 |
| 8 | 「節流中」是第五種 status | 已修正（`throttled` 旗標 + `[auto]` 覆蓋）|

## 新檢查

### 1. D7 v3 的「nginx 在 config parse 時解析字面 hostname」主張 → **成立**

三層佐證：

- **(a) 機制**：`upstream { server <name>:<port>; }` 與字面式 `proxy_pass` 在**設定載入時**用系統 resolver 解析一次、**不走** `resolver` 指令；失敗是 fatal（`[emerg] host not found in upstream`），master 直接中止。開源 nginx 無 `server ... resolve;`（那是 NGINX Plus）。
- **(b) 反證法**：plan 自己引的逃生口（`resolver 127.0.0.11` + 變數式 `proxy_pass $upstream;`）**之所以存在，正是因為字面形式在載入時就解析完了**。
- **(c) 本機實體佐證**：
  - `etchai/nginx/conf.d/etchai.conf:1-3` → `upstream django { server backend:8000; }`，compose `:160-161` 有 `depends_on: backend` 保護 —— **`depends_on` 的存在本身就是這條啟動順序約束的產物**
  - `lifetool/deploy/nginx/lifetool.conf:11-13` → `upstream lifetool { server lifetool_web:8000; }`，來自**另一個 compose project** → `etchai_nginx` **沒有也不可能有** `depends_on` 保護

→ **這條耦合今天已存在於該 VPS 上**：`lifetool_web` 不在時 `etchai_nginx` 現在就起不來。plan 把它稱為「既有的隱性耦合」是對實體檔案的準確描述、非推測。走 v2 只會多埋一顆同樣的雷。

**精度說明（加強而非削弱）**：失效在 **start**、不在 **reload**（reload 遇解不開的 upstream 會被拒絕、跑著的 master 續用舊設定）。租戶真正掉的時機是下一次 container start / restart / host 重開。plan 用字正是「**啟動失敗**」—— 精準、未誇大。且 smalldick 走自己的 compose project → etchai 的 compose **無法** `depends_on` 它，兩個 `restart` 容器在 host 重開時啟動順序不確定 → **真實 race、非理論風險**。

**另一半也成立**：`proxy_pass http://172.17.0.1:20080` 無名稱解析 → smalldick 沒起時 nginx 照常啟動、只是 502，正好滿足 issue #1「本工具故障不得影響同機其他服務」。

### 2. 殘留舊寫法 grep → **零殘留**

`127.0.0.1` ×3 全在「歷史 / 已拒絕」語境；`etchai_etchai_network` ×3 同理；`smalldick_web` ×2 是 compose 容器名（非 hostname upstream）；`172.17.0.1:20080` 在 Context / Decisions / Approach / Acceptance **全鏈一致**；現行規則已無 `expose` 寫法。

### 3. `## 變更記錄` 紀律 → **符合**

11 條全為「日期 + 設計怎麼變 + （來源：…）」；無任何輪次 / verdict / strike 進度敘述（那些正確地放在 issue #1 comment）。「（來源：self-review r1 finding #N）」是 `shared_plan_schema.md:523-524` 官方範例同款的**合規正例**（review 是歸因、不是被記錄的事件）。推翻條目 append-only、未回頭改寫。

## Findings（本輪新增）：**無**

## 觀察區（⚠️ 非 finding、不影響 verdict）

1. D7「IP 字面值的代價」只列 502 一種症狀；實際還有 `-p 172.17.0.1:...` bind 失敗 → smalldick 自己起不來。**偏保守、非低估。**
2. Approach step 1 骨架清單漏列 `docker-compose.prod.yml` 與 `deploy/nginx/`（後續步驟寫得明確無歧義）。→ **本輪已補**
3. `## Doc Sync Scope` audit-only 的 etchai `docs/` 措辭帶 D6 v1 語感；但「檔案會 scp 進該 VPS 目錄、要不要在他們 deploy 文件提一句」的 audit 問題仍成立。→ **本輪已改寫措辭**
4. 變更記錄兩處 `[struct]` 屬保守過度宣告（無害：`shared_plan_schema.md:362` 明訂 `[struct]` 計數點在 issue comment 的 Codex verdict、不在 plan 變更記錄）。
5. worktree 已有未追蹤實作檔而 label 仍 `pre-plan` —— v1.9 `pre-plan → code-review-ok` 是 agent 自主窗口故不必然違規，但屬 workflow 面提請注意。→ **本輪連同 plan-review-ok / ready-coding 一併翻正**

## VERDICT: PASS
