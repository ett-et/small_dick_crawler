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
    monkeypatch.setattr(main, "_throttle", {}, raising=False)
    # THROTTLE_SECONDS 是 import 時從 env 讀進來的 module 常數 —— 測試必須顯式釘住，
    # 否則跑測試的 shell 若剛好 export 了 SMALLDICK_THROTTLE_SECONDS=0，節流測試會假性失敗。
    monkeypatch.setattr(main, "THROTTLE_SECONDS", 10, raising=False)
    app = main.create_app()
    app.config.update(TESTING=True)
    return app.test_client(), tmp_path, monkeypatch


def stub_ok(monkeypatch, html=HTML):
    monkeypatch.setattr(iec, "fetch_html", lambda *a, **k: html)


def stub_fail(monkeypatch, exc):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(iec, "fetch_html", boom)


def test_index_renders_two_buttons_and_explanation(env):
    client, _, _ = env
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "檢查版本" in body
    assert "建立基準" in body
    assert "怎麼判斷「有更新」？" in body, "頁面必須說明判斷方式"
    assert "publication/85813" in body


def test_check_button_disabled_without_baseline(env):
    client, _, _ = env
    body = client.get("/").get_data(as_text=True)
    assert 'id="btn-check"' in body and "disabled" in body


def test_check_without_baseline_returns_no_baseline(env):
    client, data_dir, mp = env
    stub_ok(mp)
    d = client.post("/api/check").get_json()
    assert d["status"] == "no_baseline"
    assert store.read_baseline(data_dir) is None, "檢查⛔不得建立基準"


def test_healthz(env):
    client, _, _ = env
    assert client.get("/healthz").status_code == 200


def test_set_baseline_creates_it(env):
    client, data_dir, mp = env
    stub_ok(mp)
    d = client.post("/api/baseline").get_json()
    assert d["status"] == "baseline_set"
    assert d["had_previous"] is False
    assert d["snapshot"]["current_edition"] == "4.0"
    saved = store.read_baseline(data_dir)
    assert saved is not None and saved["established_at"]


def test_check_after_baseline_reports_no_update(env):
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    d = client.post("/api/check").get_json()  # 不同動作、各自節流
    assert d["status"] == "no_update"
    assert d["changes"] == []


def test_check_never_overwrites_baseline(env):
    """D8 核心：偵測到更新後再檢查一次，仍然是「有更新」（訊號不會被自己抹掉）。"""
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    before = json.dumps(store.read_baseline(data_dir), sort_keys=True)

    stub_ok(mp, HTML.replace('"edition":"4.0"', '"edition":"9.9"'))
    first = client.post("/api/check").get_json()
    assert first["status"] == "updated"

    mp.setattr(main, "_throttle", {})
    second = client.post("/api/check").get_json()
    assert second["status"] == "updated", "檢查不寫基準 → 更新訊號必須留著"
    assert json.dumps(store.read_baseline(data_dir), sort_keys=True) == before


def test_set_baseline_acknowledges_the_update(env):
    """按了更新基準之後，同一個變化就不再算「有更新」。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")

    stub_ok(mp, HTML.replace('"edition":"4.0"', '"edition":"9.9"'))
    assert client.post("/api/check").get_json()["status"] == "updated"

    mp.setattr(main, "_throttle", {})
    ack = client.post("/api/baseline").get_json()
    assert ack["status"] == "baseline_set" and ack["had_previous"] is True and ack["changes"]

    mp.setattr(main, "_throttle", {})
    assert client.post("/api/check").get_json()["status"] == "no_update"


def test_changed_page_reports_updated_with_before_after(env):
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")

    stub_ok(mp, HTML.replace('"edition":"4.0"', '"edition":"9.9"'))
    d = client.post("/api/check").get_json()

    assert d["status"] == "updated"
    assert d["changes"], "有更新時必須列出變動欄位"
    for c in d["changes"]:
        assert "before" in c and "after" in c and c["label"]


def test_error_does_not_overwrite_baseline(env):
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    before = json.dumps(store.read_baseline(data_dir), sort_keys=True)

    stub_fail(mp, iec.FetchError("連線逾時"))
    mp.setattr(main, "_throttle", {})
    d = client.post("/api/baseline").get_json()

    assert d["status"] == "error"
    assert "逾時" in d["message"]
    after = json.dumps(store.read_baseline(data_dir), sort_keys=True)
    assert before == after, "檢查失敗時基準檔不得被覆寫"


def test_parse_error_is_not_silently_no_update(env):
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    before = json.dumps(store.read_baseline(data_dir), sort_keys=True)

    stub_ok(mp, "<html>目標頁面改版了</html>")
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

    first = client.post("/api/baseline").get_json()
    second = client.post("/api/baseline").get_json()

    assert calls["n"] == 1, "節流期間不得再對 IEC 發請求"
    assert second["throttled"] is True
    assert second["status"] == first["status"]
    assert second["status"] in {"baseline_set", "no_baseline", "no_update", "updated", "error"}, \
        "節流不是額外的 status"


def test_actions_do_not_block_each_other(env):
    """回歸：一個動作在抓取途中，⛔ 不得卡住另一個動作（含只讀快取的那條路）。

    code review 2026-09-04 抓到：原本 `_throttled` 在持有**全域**鎖的情況下呼叫
    `fn()`（內含最長 30 秒的對外請求）→ 另一條 thread 連讀快取都要等 30 秒。
    """
    import threading

    client, _, mp = env
    started = threading.Event()
    release = threading.Event()

    def slow(*a, **k):
        started.set()
        release.wait(5)
        return HTML

    mp.setattr(iec, "fetch_html", slow)

    # 先建好基準（用一次 slow，但立刻放行）
    release.set()
    client.post("/api/baseline")
    release.clear()
    started.clear()

    box = {}

    def hold_check():
        box["check"] = client.post("/api/check").get_json()

    t = threading.Thread(target=hold_check, daemon=True)
    t.start()
    assert started.wait(3), "check 應該已經進到抓取階段"

    # check 正卡在抓取中 —— baseline 這個動作 MUST 不受影響
    done = threading.Event()

    def other():
        box["baseline"] = client.post("/api/baseline").get_json()
        done.set()

    t2 = threading.Thread(target=other, daemon=True)
    t2.start()
    hit_cache = done.wait(2)   # 有快取 → 應該立刻回，⛔ 不該被 check 的鎖擋住

    release.set()
    t.join(5)
    t2.join(5)

    assert hit_cache, "另一個動作被卡住了 —— per-key 鎖沒生效"
    assert box["baseline"]["throttled"] is True


def test_no_baseline_is_not_cached_by_throttle(env):
    """回歸：no_baseline 沒有對外發請求 → ⛔ 不得被節流快取。

    2026-09-04 本機實測踩到：建立基準後再按檢查，仍回被快取的 no_baseline。
    """
    client, _, mp = env
    stub_ok(mp)
    assert client.post("/api/check").get_json()["status"] == "no_baseline"
    client.post("/api/baseline")
    d = client.post("/api/check").get_json()   # ⛔ 不重設節流
    assert d["status"] == "no_update", "建立基準後的檢查不得回到被快取的 no_baseline"
    assert d.get("throttled") is False


def test_no_baseline_response_has_no_internal_flag(env):
    client, _, mp = env
    stub_ok(mp)
    assert "_fetched" not in client.post("/api/check").get_json()


def test_throttle_is_per_action(env):
    """按了「更新基準」不該把「檢查版本」也一起鎖住。"""
    client, _, mp = env
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return HTML

    mp.setattr(iec, "fetch_html", counting)
    client.post("/api/baseline")
    d = client.post("/api/check").get_json()
    assert calls["n"] == 2, "兩個動作各自節流"
    assert d.get("throttled") is False


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
