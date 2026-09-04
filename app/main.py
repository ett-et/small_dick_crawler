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

from flask import Flask, jsonify, render_template

from . import iec, store

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
        return render_template(
            "index.html",
            source_url=iec.DEFAULT_URL,
            baseline=store.read_baseline(data_dir),
            last_check=store.read_last_check(data_dir),
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
                return jsonify(cached), 200

        result = fn()
        if result.pop("_fetched", True):
            _throttle[key] = {"at": time.monotonic(), "result": result}
        return jsonify(result), 200


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
    """建立 / 更新基準。抓取或解析失敗 → 不覆寫既有基準。"""
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
    """檢查版本。⛔ 任何情況都不寫基準；只寫「上次檢查」紀錄。"""
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
    return result


app = create_app()
