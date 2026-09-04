"""endpoint 層測試 —— 外部抓取一律以 fixture stub 掉，⛔ 不連外網。"""

import json
from pathlib import Path

import pytest

from app import iec, main, store

FIXTURE = Path(__file__).parent / "fixtures" / "publication_85813.html"
HTML = FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """每個測試一份乾淨的 data dir + 歸零的節流狀態。"""
    monkeypatch.setenv("SMALLDICK_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_last_fetch_at", 0.0, raising=False)
    monkeypatch.setattr(main, "_last_result", None, raising=False)
    app = main.create_app()
    app.config.update(TESTING=True)
    return app.test_client(), tmp_path, monkeypatch


def stub_ok(monkeypatch, html=HTML):
    monkeypatch.setattr(iec, "fetch_html", lambda *a, **k: html)


def stub_fail(monkeypatch, exc):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(iec, "fetch_html", boom)


def test_index_renders_button(env):
    client, _, _ = env
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "check new" in body
    assert "publication/85813" in body


def test_healthz(env):
    client, _, _ = env
    assert client.get("/healthz").status_code == 200


def test_first_check_creates_baseline(env):
    client, data_dir, mp = env
    stub_ok(mp)
    d = client.post("/api/check").get_json()
    assert d["status"] == "baseline_created"
    assert d["changes"] == []
    assert d["snapshot"]["current_edition"] == "4.0"
    assert store.read_baseline(data_dir) is not None


def test_second_check_reports_no_update(env):
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/check")
    main._last_fetch_at = 0.0  # 略過節流，測「第二次真的去抓」
    d = client.post("/api/check").get_json()
    assert d["status"] == "no_update"
    assert d["changes"] == []


def test_changed_page_reports_updated_with_before_after(env):
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/check")

    stub_ok(mp, HTML.replace('"edition":"4.0"', '"edition":"9.9"'))
    main._last_fetch_at = 0.0
    d = client.post("/api/check").get_json()

    assert d["status"] == "updated"
    assert d["changes"], "有更新時必須列出變動欄位"
    for c in d["changes"]:
        assert "before" in c and "after" in c and c["label"]


def test_error_does_not_overwrite_baseline(env):
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/check")
    before = json.dumps(store.read_baseline(data_dir), sort_keys=True)

    stub_fail(mp, iec.FetchError("連線逾時"))
    main._last_fetch_at = 0.0
    d = client.post("/api/check").get_json()

    assert d["status"] == "error"
    assert "逾時" in d["message"]
    after = json.dumps(store.read_baseline(data_dir), sort_keys=True)
    assert before == after, "檢查失敗時基準檔不得被覆寫"


def test_parse_error_is_not_silently_no_update(env):
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/check")
    before = json.dumps(store.read_baseline(data_dir), sort_keys=True)

    stub_ok(mp, "<html>目標頁面改版了</html>")
    main._last_fetch_at = 0.0
    d = client.post("/api/check").get_json()

    assert d["status"] == "error"
    assert "解析" in d["message"]
    assert json.dumps(store.read_baseline(data_dir), sort_keys=True) == before


def test_throttle(env):
    """10 秒內重複請求：不對外發新請求，回上次 status + throttled 旗標。"""
    client, _, mp = env

    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return HTML

    mp.setattr(iec, "fetch_html", counting)

    first = client.post("/api/check").get_json()
    second = client.post("/api/check").get_json()

    assert calls["n"] == 1, "節流期間不得再對 IEC 發請求"
    assert second["throttled"] is True
    assert second["status"] == first["status"]
    assert second["status"] in {"baseline_created", "no_update", "updated", "error"}, \
        "節流不是第五種 status"


def test_baseline_survives_missing_file(tmp_path):
    assert store.read_baseline(tmp_path) is None


def test_baseline_write_is_atomic_and_readable(tmp_path):
    snap = {"current_edition": "4.0", "checked_at": "2026-09-04T10:00:00+08:00"}
    store.write_baseline(snap, tmp_path)
    assert store.read_baseline(tmp_path) == snap
    # 不留暫存檔
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".baseline-")]


def test_corrupt_baseline_is_treated_as_absent(tmp_path):
    store.baseline_path(tmp_path).write_text("{ not json", encoding="utf-8")
    assert store.read_baseline(tmp_path) is None
