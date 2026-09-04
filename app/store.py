"""狀態檔的讀寫（基準 + 上次檢查紀錄）。

設計依據見 plan D3：單一目錄下的 JSON 檔 + atomic write + docker volume。
atomic 的理由 —— issue #1 `## Edge Cases`「同時多人按按鈕不得寫壞基準檔」。

兩個檔各自獨立（per D8 兩顆按鈕拆分）：
- `baseline.json`   —— 基準快照，只有按「建立 / 更新基準」才會被寫
- `last_check.json` —— 上次檢查的時間與結果，按「檢查版本」時寫
分開存的理由：檢查**不覆寫基準**，故兩者的寫入時機不同，混在同一個檔會需要
read-modify-write，反而把原本單純的原子寫變複雜。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("SMALLDICK_DATA_DIR", "/data"))
BASELINE_NAME = "baseline.json"
LAST_CHECK_NAME = "last_check.json"


def _dir(data_dir: Path | None) -> Path:
    return data_dir or DEFAULT_DATA_DIR


def _read_json(name: str, data_dir: Path | None) -> dict | None:
    """讀一個 JSON 檔。不存在回 None；壞檔也回 None（當成沒有）。"""
    try:
        with (_dir(data_dir) / name).open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(name: str, payload: dict, data_dir: Path | None) -> None:
    """原子寫入：同目錄建暫存檔 → fsync → os.replace 換名。

    同目錄是必要條件 —— os.replace 只在同一個 filesystem 內保證原子。
    """
    path = _dir(data_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def baseline_path(data_dir: Path | None = None) -> Path:
    return _dir(data_dir) / BASELINE_NAME


def read_baseline(data_dir: Path | None = None) -> dict | None:
    return _read_json(BASELINE_NAME, data_dir)


def write_baseline(snapshot: dict, data_dir: Path | None = None) -> None:
    _write_json(BASELINE_NAME, snapshot, data_dir)


def read_last_check(data_dir: Path | None = None) -> dict | None:
    return _read_json(LAST_CHECK_NAME, data_dir)


def write_last_check(record: dict, data_dir: Path | None = None) -> None:
    _write_json(LAST_CHECK_NAME, record, data_dir)
