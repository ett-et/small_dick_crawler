"""Flask app —— 單頁 + 一個檢查 endpoint。

設計依據見 plan D1 / D5。
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
_lock = threading.Lock()
_last_fetch_at: float = 0.0
_last_result: dict | None = None


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
        baseline = store.read_baseline(_data_dir())
        return render_template(
            "index.html",
            source_url=iec.DEFAULT_URL,
            baseline=baseline,
        )

    @app.post("/api/check")
    def check():
        global _last_fetch_at, _last_result

        with _lock:
            elapsed = time.monotonic() - _last_fetch_at
            if _last_result is not None and elapsed < THROTTLE_SECONDS:
                # 節流不是第五種 status（plan D5）：回上次那次的 status + throttled 旗標。
                throttled = dict(_last_result)
                throttled["throttled"] = True
                throttled["throttle_wait_seconds"] = round(THROTTLE_SECONDS - elapsed, 1)
                return jsonify(throttled), 200

            result = _run_check()
            _last_fetch_at = time.monotonic()
            _last_result = result
            return jsonify(result), 200

    return app


def _run_check() -> dict:
    """跑一次真正的檢查。任何失敗都不覆寫基準（issue #1 `## Business Rules`）。"""
    data_dir = _data_dir()

    try:
        html = iec.fetch_html()
        blocks = iec.extract_blocks(html)
    except iec.FetchError as exc:
        return {
            "status": "error",
            "throttled": False,
            "message": f"抓取失敗：{exc}",
            "checked_at": iec.now_iso(),
        }
    except iec.ParseError as exc:
        return {
            "status": "error",
            "throttled": False,
            "message": f"解析失敗：{exc}",
            "checked_at": iec.now_iso(),
        }

    current = iec.normalize(blocks)
    current["checked_at"] = iec.now_iso()

    baseline = store.read_baseline(data_dir)

    if baseline is None:
        store.write_baseline(current, data_dir)
        return {
            "status": "baseline_created",
            "throttled": False,
            "message": "已建立基準（第一次檢查，沒有可比對的上次紀錄）",
            "snapshot": current,
            "changes": [],
            "checked_at": current["checked_at"],
        }

    changes = iec.diff(baseline, current)

    if not changes:
        store.write_baseline(current, data_dir)  # 只更新 checked_at
        return {
            "status": "no_update",
            "throttled": False,
            "message": "沒有更新",
            "snapshot": current,
            "changes": [],
            "previous_checked_at": baseline.get("checked_at"),
            "checked_at": current["checked_at"],
        }

    store.write_baseline(current, data_dir)
    return {
        "status": "updated",
        "throttled": False,
        "message": f"有更新（{len(changes)} 個欄位變動）",
        "snapshot": current,
        "changes": changes,
        "previous_checked_at": baseline.get("checked_at"),
        "checked_at": current["checked_at"],
    }


app = create_app()
