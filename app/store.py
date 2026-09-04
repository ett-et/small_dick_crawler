"""基準（baseline）的讀寫。

設計依據見 plan D3：單一 JSON 檔 + atomic write + docker volume。
atomic 的理由 —— issue #1 `## Edge Cases`「同時多人按按鈕不得寫壞基準檔」。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("SMALLDICK_DATA_DIR", "/data"))
BASELINE_NAME = "baseline.json"


def baseline_path(data_dir: Path | None = None) -> Path:
    return (data_dir or DEFAULT_DATA_DIR) / BASELINE_NAME


def read_baseline(data_dir: Path | None = None) -> dict | None:
    """讀基準。不存在回 None；壞檔也回 None（當成沒有基準、下次覆寫）。"""
    path = baseline_path(data_dir)
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_baseline(snapshot: dict, data_dir: Path | None = None) -> None:
    """原子寫入：同目錄建暫存檔 → fsync → os.replace 換名。

    同目錄是必要條件 —— os.replace 只在同一個 filesystem 內保證原子。
    """
    path = baseline_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".baseline-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
