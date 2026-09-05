# `docs/ssot/` — 本 repo 的業務 SSOT（規則本體）

> ⚠️ **這張索引是手寫的。**
> 母框架 `repo_ssot_layout.md §8` 規定索引由 `scripts/generate_aipjindex.py` 掃 `docs/ssot/` **機器生**，寫進 `aiPJINDEX.md` 的機器生成區塊。
> **本 repo 沒有那支 generator**（`aiPJINDEX.md` 檔頭已註明整份索引為手寫）→ 這裡改用手寫，**⛔ 不假裝有 generator**。
> **紅線：新增 / 刪除 `docs/ssot/*.md` 時 MUST 同步這張表**（手寫清單必漂，這是已知代價）。
> 日後若把 generator 接進來，機器生索引會落在 `aiPJINDEX.md`，**本檔屆時應刪除**、⛔ 不留成第二份索引。
>
> ⛔ **本檔本身不是 domain SSOT**（無 frontmatter、不承載任何規則），只是索引 + domain 判定紀錄。

## 索引（6 欄，欄位定義 per `repo_ssot_layout.md §8`）

| name | canonical path | scope | override 規則 | change gate | domain-load trigger |
|---|---|---|---|---|---|
| Business Logic SSOT — 版本檢查的判定與基準規則 | `docs/ssot/business_logic.md` | 「有沒有更新」怎麼判、基準誰能寫、失敗怎麼算、對目標站點怎麼發請求 | `local-extends-not-overrides` | `human-review-§2.6`（repo 級 PR + review）| 動判定邏輯 / 基準寫入 / 節流 / 失敗處理 / 新增檢查來源之前 |
| API Contract SSOT — 頁面與後端交換資料的契約 | `docs/ssot/api_contract.md` | 兩個動作 endpoint 的語意分工、結果狀態值域、回應欄位、健康檢查與前端交換面的約束 | `local-extends-not-overrides` | `human-review-§2.6`（repo 級 PR + review）| 動 endpoint / 回應欄位 / status 值域 / 前端渲染對照表之前 |

## 七條 domain 的逐條判定（per `repo_ssot_layout.md §3`）

`§10` 明訂「⛔ 登錄 ≠ 每個 repo 都要建 7 個檔；用不到的 domain ⛔ 非待辦」。
以下逐條給結論 —— **不適用者明寫理由、⛔ 不建空殼檔**。

| # | domain | 結論 | 理由 |
|---|---|---|---|
| 1 | RBAC（系統權限）| **不適用** | 系統裡**沒有角色、沒有帳號、沒有登入** —— 頁面對所有人公開，唯一的兩個動作對所有訪客一致（issue #1 `## Permission`；`app/main.py` 全部 route 無任何認證 / 授權判斷）。沒有權限模型可寫。|
| 2 | 營運角色 | **不適用（兩重）** | (a) 該 domain 的落點是 **ops repo**（組織現實）、不是產品 repo；(b) 本 repo 是**測試場工具**、不承載任何事業體營運資料（`CLAUDE.md ## 身分 / 定位`）。|
| 3 | 職能 | **不適用（同上兩重）** | 同第 2 條。|
| 4 | Access Control（仲裁層）| **不適用** | `§4` 定義它是「RBAC / 營運角色 / 職能**三套交會時誰贏**」的仲裁層，且 `§11` 明禁把它寫成第 4 份角色清單。本 repo **三個上游輸入全空** → 沒有東西可仲裁，寫出來只會是一句「大家都一樣」。<br>⚠️ 唯一具存取控制形狀的規則 =「無登入、基準是全站共用單一份、任何訪客都能覆寫它（v1 明示接受）」—— 它是**基準寫入權**的一部分，已落 `business_logic.md` **R-B5**，⛔ 不另立檔（`§5` 一 domain 一檔，切檔單位是 domain、不是「像不像」）。|
| 5 | Approval Flow | **不適用** | 沒有簽核、沒有多方放行、沒有狀態流轉需要誰同意。<br>⚠️ 唯一像「確認」的東西 =「人按下『建立／更新基準』＝『我知道了』」，但那是**單人、單步、無審批對象**的動作語意，屬業務邏輯 → 落 `business_logic.md` **R-B3**。把它寫成 approval flow 會是為了填格式而膨脹（issue #4 `## Technical Constraints` 明禁）。|
| 6 | **Business Logic**（含資料邏輯）| **適用 → `docs/ssot/business_logic.md`** | 這是本 repo **真正有規則**的地方：判定「有更新」的欄位與方式、基準寫入權、失敗不得靜默、對外請求的節流與 on-demand 紅線。|
| 7 | **API Contract** | **適用 → `docs/ssot/api_contract.md`** | 兩個動作的讀 / 寫語意、封閉的 `status` 五值域、回應必有欄位、節流以旗標而非狀態表達 —— 這些改了 code 必須跟著改（`§2` 判準）。|

**兩條不進本批的**（per `§3.1`）：Module Catalog 併入地圖層 Feature Map、Frontend Architecture pointer 回 `frontend_governance.md` —— 本 repo 不重複處理。

## 邊界（⛔ 不做的事）

- ⛔ **不上母框架 registry**：repo 級業務 SSOT 依 `repo_ssot_layout.md §9` 不登錄 `project_maker/standards/ssot_registry.md`；discoverability 就靠本 repo 自己（本檔 + `aiPJINDEX.md`）。
- ⛔ **不重抄母框架規則**：本目錄下的檔案只 pointer 回 `~/projects/project_maker/standards/*`。
- ⛔ **不列舉現況**：SSOT 只寫規則。「現在長什麼樣」屬地圖層（`docs/specs/`），方向恆為 **地圖 ──pointer──▶ SSOT ──約束──▶ code**、⛔ 不互相追（`§7`）。
- ⛔ **不臆造**：規則還沒定的地方一律標 `TBD` 並指向對應的 issue，⛔ 不自行拍板（per `behavioral_constraints.md §2.8`）。

### 目前的 TBD 一覽

| TBD | 在哪 | 指向哪張票 |
|---|---|---|
| TBD-1｜「來源（target）」作為一級概念尚未定義（沒有名稱、沒有清單、沒有可設定性）| `business_logic.md §1` | `#3`（需要「目標名稱」）+ 未來的**多來源票（尚未開）**|
| TBD-2｜「上次檢查」紀錄要存到什麼程度（現存欄位不足以重建匯出表）| `business_logic.md §6` | `#3` `## Open Questions` #2 |
| TBD-3｜匯出下載的 endpoint 契約（資料來源 / `.xlsx` vs CSV / 失敗列 / 按鈕亮起條件）| `api_contract.md` | `#3` `## Open Questions` #1–#4 |
