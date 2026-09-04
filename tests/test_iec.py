"""解析與比對的離線測試 —— 一律用 fixture，⛔ 不連外網。"""

import json
from pathlib import Path

import pytest

from app import iec

FIXTURE = Path(__file__).parent / "fixtures" / "publication_85813.html"


@pytest.fixture
def html():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def snapshot(html):
    return iec.normalize(iec.extract_blocks(html))


def test_extracts_current_edition_and_date(snapshot):
    # plan acceptance：從實際 HTML fixture 解出 edition 4.0 / 2023-05-26
    assert snapshot["current_edition"] == "4.0"
    assert snapshot["current_publication_date"] == "2023-05-26"
    assert snapshot["current_reference"] == "IEC 62368-1:2023"


def test_extracts_full_lifecycle_history(snapshot):
    assert len(snapshot["lifecycle_entries"]) == 4
    editions = {e["edition"] for e in snapshot["lifecycle_entries"]}
    assert editions == {"1.0", "2.0", "3.0", "4.0"}


def test_extracts_under_development(snapshot):
    under = snapshot["under_development"]
    assert under["reference"] == "IEC 62368-1/AMD1"
    assert under["stage"] == "PCC"
    assert under["status"] == "PREPARING"
    assert under["forecast_pub_date"] == "2027-12-31"


def test_missing_lifecycles_raises():
    # 紅線：解析不到 lifecycles 必須明確失敗，⛔ 不可靜默回空結果
    with pytest.raises(iec.ParseError):
        iec.extract_blocks("<html><body>目標頁面改版了</body></html>")


def test_malformed_lifecycles_raises():
    with pytest.raises(iec.ParseError):
        iec.extract_blocks('<script>lifecycles: {"v4": oops}</script>')


def test_missing_under_development_ok(html):
    # underDevelopmentProduct 缺席是合法的（代表目前沒有開發中版本）
    stripped = html[: html.index("underDevelopmentProduct")] + html[html.index("lifecycles:") :]
    snap = iec.normalize(iec.extract_blocks(stripped))
    assert snap["under_development"] is None
    assert snap["current_edition"] == "4.0"


def test_diff_without_baseline_is_empty(snapshot):
    assert iec.diff(None, snapshot) == []


def test_diff_identical_is_empty(snapshot):
    same = json.loads(json.dumps(snapshot))
    assert iec.diff(snapshot, same) == []


def test_diff_detects_signal_a_edition_change(snapshot):
    """訊號 A：目前版次變動。"""
    changed = json.loads(json.dumps(snapshot))
    changed["current_edition"] = "5.0"
    changes = iec.diff(snapshot, changed)
    assert [c["field"] for c in changes] == ["current_edition"]
    assert changes[0]["before"] == "4.0"
    assert changes[0]["after"] == "5.0"


def test_diff_detects_signal_b_new_lifecycle_entry(snapshot):
    """訊號 B：冒出更新的版次。"""
    changed = json.loads(json.dumps(snapshot))
    changed["lifecycle_entries"].append(
        {
            "key": "v5",
            "reference": "IEC 62368-1:2028",
            "edition": "5.0",
            "publication_date": "2028-01-01",
            "status": "PUBLISHED",
        }
    )
    assert [c["field"] for c in iec.diff(snapshot, changed)] == ["lifecycle_entries"]


def test_diff_detects_signal_c_under_development_change(snapshot):
    """訊號 C：開發中版本狀態變動。"""
    changed = json.loads(json.dumps(snapshot))
    changed["under_development"]["stage"] = "CDV"
    assert [c["field"] for c in iec.diff(snapshot, changed)] == ["under_development"]


def test_diff_detects_under_development_disappearing(snapshot):
    """issue #1 Edge Cases：開發中版本從「有」變「沒有」也算有更新。"""
    changed = json.loads(json.dumps(snapshot))
    changed["under_development"] = None
    assert [c["field"] for c in iec.diff(snapshot, changed)] == ["under_development"]


def test_checked_at_not_compared(snapshot):
    """checked_at 每次都不同，若參與比對就會永遠誤報「有更新」。"""
    a = json.loads(json.dumps(snapshot))
    a["checked_at"] = "2026-09-04T10:00:00+08:00"
    b = json.loads(json.dumps(snapshot))
    b["checked_at"] = "2026-09-04T11:00:00+08:00"
    assert iec.diff(a, b) == []


def test_normalize_is_stable(html):
    """同樣的頁面必須產出同樣的結構（否則 dict 順序抖動會誤報有更新）。"""
    a = iec.normalize(iec.extract_blocks(html))
    b = iec.normalize(iec.extract_blocks(html))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
