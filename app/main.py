"""Flask app —— 單頁 + 兩個動作 endpoint。

設計依據見 plan D1 / D5 / D8。

D8 兩顆按鈕的核心語意（與單顆按鈕時期的差別）：
- 「建立 / 更新基準」**寫**基準
- 「檢查版本」**只讀不寫**基準 → 偵測到的更新會**一直留著**，直到人按下更新基準為止
  （單顆按鈕時期，檢查完就順手覆寫基準 → 再按一次就變「沒有更新」，
    等於把「有東西變了」這個訊號自己抹掉。）
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from . import export, iec, sources, store

THROTTLE_SECONDS = int(os.environ.get("SMALLDICK_THROTTLE_SECONDS", "10"))

# 節流狀態。單 worker + 少量執行緒 → 程序內狀態即足夠（plan D5）。
# 兩個動作各自計時、且各自一把鎖：按了「檢查」不該把「更新基準」也一起鎖住。
#
# ⛔ 為什麼不是一把全域鎖（code review 2026-09-04 抓到）：
# `fn()` 內含最長 30 秒的對外請求。若在持有全域鎖的情況下呼叫它，
# gunicorn 的另一條 thread 連「讀快取」都會被卡住整整 30 秒 ——
# 兩個動作互相癱瘓、連 throttled 的快速回應都拿不到。
# 改成 per-key 鎖：同一個動作併發 → 後到的等前一個做完拿快取（正確、不重複打 IEC）；
# 不同動作 → 互不阻擋。
_registry_lock = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_throttle: dict[str, dict] = {}


def _lock_for(key: str) -> threading.Lock:
    with _registry_lock:
        return _locks.setdefault(key, threading.Lock())


# ── 匯出快照（issue #3 D2）────────────────────────────────────────────────
#
# 「最近一次『檢查版本』的結果」，⛔ **完全不落檔** —— 沒有檔案就沒有殘留、沒有累積、
# 容器重啟自動乾淨。可行的前提是 gunicorn **`--workers 1`**（既有紅線、見 `aiREAD.md §6`）：
# 單一程序 → 程序內記憶體就是唯一狀態。
#
# ⚠️ 這條紅線因此又多綁一個東西：改成多 worker 不只會壞掉節流，**也會壞掉匯出**。
#
# 只是整個 dict 的換手（重新綁定 module attribute），⛔ 沒有 read-modify-write，
# 故不需要額外的鎖。
_export: dict | None = None


def _set_export(result: dict) -> None:
    """記住這一次的檢查結果供匯出。新的蓋掉舊的 —— 永遠只留一份。"""
    global _export
    _export = {
        "status": result.get("status"),
        "message": result.get("message"),
        "snapshot": result.get("snapshot"),
        "checked_at": result.get("checked_at"),
    }


def _clear_export() -> None:
    global _export
    _export = None


def _data_dir() -> Path | None:
    raw = os.environ.get("SMALLDICK_DATA_DIR")
    return Path(raw) if raw else None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return "ok", 200

    @app.get("/")
    def index():
        data_dir = _data_dir()

        # ⚠️⚠️ 誠實界定：**這裡讓 GET 帶副作用** —— HTTP 語意上 GET 應該是 safe method、
        # 不改變伺服器狀態，本行明確違反它。
        #
        # 這是為了精確實現 issue #3 D2「丙：重整後清空、同一次頁面內可重複下載」付出的代價，
        # **Human 已知悉並記在 issue #3 `## Decisions` D2 連帶影響裡**，⛔ 不是疏忽。
        # 替代做法（前端產 session token、後端按 token 存）能保住 GET 純淨，
        # 但要多一套機制 —— 以本工具的規模不划算。
        #
        # `X-Panel: 1` 豁免（plan I2）：既有前端在每次成功動作後會呼叫 `refreshPanel()`
        # **再打一次 `GET /`** 來刷新上方面板（見 `templates/index.html`）。那是「局部面板刷新」、
        # ⛔ **不是**「開頁 / 重整」。若不豁免，檢查完的下一個 request 就把匯出清掉，
        # D1「檢查後按鈕變亮」根本無法成立。
        if request.headers.get("X-Panel") != "1":
            _clear_export()

        return render_template(
            "index.html",
            targets=sources.SOURCES,
            baseline=store.read_baseline(data_dir),
            last_check=store.read_last_check(data_dir),
            export_ready=_export is not None,
        )

    @app.get("/api/export.csv")
    def export_csv():
        """下載「最近一次檢查版本」的結果快照（issue #3）。

        ⛔ **本 endpoint 一律不對 IEC 發任何請求**（issue #3 紅線）—— 它只讀程序內的
        `_export`，連 `store` 都不碰。
        ⛔ **下載不清除** —— 同一次頁面內可重複下載（D2 丙）。
        """
        snapshot = _export
        if snapshot is None:
            # 409 而不是 404：這個 endpoint 一直存在，只是**當下沒有可匯出的結果**。
            # ⛔ 不回 200 + 空檔 —— 靜默失敗違反本 repo「失敗要吵」的一貫紅線。
            return jsonify({"status": "no_export", "message": "目前沒有可下載的檢查結果 —— 請先按「檢查版本」。"}), 409

        payload = export.to_csv_bytes(export.rows_from_check(snapshot))
        filename = export.filename_for(snapshot.get("checked_at"))
        return Response(
            payload,
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/baseline")
    def set_baseline():
        """建立 / 更新基準 —— 抓一次、把現況寫成新的基準。"""
        return _throttled("baseline", _run_set_baseline)

    @app.post("/api/check")
    def check():
        """檢查版本 —— 抓一次、與基準比對。⛔ 不動基準。"""
        return _throttled("check", _run_check)

    return app


def _throttled(key: str, fn):
    """同一個動作在 THROTTLE_SECONDS 內重複觸發 → 回上次結果、不對外發新請求。

    ⛔ 只快取「真的去抓過 IEC」的結果。沒發出外部請求的結果（例如 no_baseline）
    快取了會說謊 —— 那種狀態會因為使用者按了另一顆按鈕而改變，卻沒有任何
    對外請求需要被節流。（2026-09-04 本機實測踩到：建立基準後再按檢查，
    仍回被快取的 no_baseline。）

    `export_ready`（issue #3 D1）**在這一層即時計算、⛔ 不進快取**：
    節流會重放 10 秒前的 result dict，若旗標被一起快取，期間有人重整過頁面就會說謊
    （按鈕亮著、但下載回 409）。與上一段的快取教訓同源。
    """
    global _throttle
    with _lock_for(key):
        entry = _throttle.get(key)
        if entry is not None:
            elapsed = time.monotonic() - entry["at"]
            if elapsed < THROTTLE_SECONDS:
                cached = dict(entry["result"])
                cached["throttled"] = True
                cached["throttle_wait_seconds"] = round(THROTTLE_SECONDS - elapsed, 1)
                cached["export_ready"] = _export is not None
                return jsonify(cached), 200

        result = fn()
        if result.pop("_fetched", True):
            _throttle[key] = {"at": time.monotonic(), "result": result}
        payload = dict(result)
        payload["export_ready"] = _export is not None
        return jsonify(payload), 200


def _fetch_snapshot() -> tuple[dict | None, dict | None]:
    """回 (snapshot, error_result)。成功時 error_result 為 None。"""
    try:
        html = iec.fetch_html()
        blocks = iec.extract_blocks(html)
    except iec.FetchError as exc:
        return None, {
            "status": "error",
            "throttled": False,
            "message": f"抓取失敗：{exc}",
            "checked_at": iec.now_iso(),
        }
    except iec.ParseError as exc:
        return None, {
            "status": "error",
            "throttled": False,
            "message": f"解析失敗：{exc}",
            "checked_at": iec.now_iso(),
        }

    snapshot = iec.normalize(blocks)
    snapshot["checked_at"] = iec.now_iso()
    return snapshot, None


def _run_set_baseline() -> dict:
    """建立 / 更新基準。抓取或解析失敗 → 不覆寫既有基準。

    ⛔ **本函式的任何路徑（含失敗路徑）都不得碰 `_export`**（issue #3 D1）：
    下載按鈕的語意固定為「匯出**檢查結果**」，只有「檢查版本」讓它亮 ——
    ⛔ 不擴成「匯出目前狀態」。
    """
    data_dir = _data_dir()
    snapshot, err = _fetch_snapshot()
    if err:
        return err

    previous = store.read_baseline(data_dir)
    snapshot["established_at"] = snapshot["checked_at"]

    changes = iec.diff(previous, snapshot) if previous else []
    store.write_baseline(snapshot, data_dir)

    return {
        "status": "baseline_set",
        "throttled": False,
        "message": (
            "已建立基準（之前沒有基準）"
            if previous is None
            else (
                f"已更新基準（與舊基準相比有 {len(changes)} 個欄位不同）"
                if changes
                else "已更新基準（與舊基準相同）"
            )
        ),
        "had_previous": previous is not None,
        "snapshot": snapshot,
        "changes": changes,
        "checked_at": snapshot["checked_at"],
    }


def _run_check() -> dict:
    """檢查版本。⛔ 任何情況都不寫基準；只寫「上次檢查」紀錄。

    本函式三條返回路徑對匯出快照（issue #3 D1 / D3）的處置：

    | 路徑 | 寫 `_export`？ | 為什麼 |
    |---|---|---|
    | `no_baseline` | ❌ | 根本沒發生比對、也沒對 IEC 發過請求 → 屬 issue #3 `## Business Rules`「**沒有可下載的結果**」（plan I4；⛔ 也不清除既有的）|
    | `error` | ✅ | D3 明文要求失敗也要輸出一列、「最新版次」欄寫失敗原因 |
    | `updated` / `no_update` | ✅ | 正常的檢查結果 |
    """
    data_dir = _data_dir()
    baseline = store.read_baseline(data_dir)

    if baseline is None:
        return {
            "status": "no_baseline",
            "throttled": False,
            "message": "還沒有基準，沒有東西可以比對 —— 請先按「建立基準」。",
            "checked_at": iec.now_iso(),
            "_fetched": False,   # 完全沒對外發請求 → ⛔ 不進節流快取
        }

    snapshot, err = _fetch_snapshot()
    if err:
        _set_export(err)   # D3：失敗也要能匯出，「最新版次」欄寫失敗原因
        return err

    changes = iec.diff(baseline, snapshot)
    result = {
        "status": "updated" if changes else "no_update",
        "throttled": False,
        "message": (
            f"有更新（{len(changes)} 個欄位與基準不同）"
            if changes
            else "沒有更新（與基準完全相同）"
        ),
        "snapshot": snapshot,
        "changes": changes,
        "baseline_established_at": baseline.get("established_at") or baseline.get("checked_at"),
        "checked_at": snapshot["checked_at"],
    }

    # ⛔ 不寫 baseline —— 只記「這次檢查發生過、結果是什麼」。
    store.write_last_check(
        {
            "checked_at": result["checked_at"],
            "status": result["status"],
            "change_count": len(changes),
        },
        data_dir,
    )
    _set_export(result)
    return result


app = create_app()
