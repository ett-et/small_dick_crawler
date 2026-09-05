"""endpoint 層測試 —— 外部抓取一律以 fixture stub 掉，⛔ 不連外網。"""

import json
from pathlib import Path

import pytest

from app import iec, main, sources, store

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
    # 匯出快照是 module-level 記憶體狀態（issue #3 D2）→ 每個測試必須從 None 起跑，
    # 否則測試之間會互相污染。
    monkeypatch.setattr(main, "_export", None, raising=False)
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
    # ⚠️ 頁面上不只一顆按鈕可能是 disabled（issue #3 加了「下載結果」）→ 只看整頁有沒有
    # "disabled" 這個字會誤放行。這裡把範圍收斂到 btn-check 自己那個 tag 內。
    assert 'id="btn-check"' in body
    frag = body[body.index('id="btn-check"'):]
    assert "disabled" in frag[: frag.index(">")]


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


# ── 檢查結果匯出 CSV（issue #3 D1–D5）────────────────────────────────────

def download_button_disabled(body: str) -> bool:
    """從渲染出來的 HTML 判斷「下載結果」那顆按鈕是不是暗的。"""
    frag = body[body.index('id="btn-download"'):]
    return "disabled" in frag[: frag.index(">")]


def test_download_button_disabled_on_fresh_page(env):
    """D1 / D2：還沒檢查過 → 下載鈕停用。"""
    client, _, _ = env
    body = client.get("/").get_data(as_text=True)
    assert 'id="btn-download"' in body and "下載結果" in body
    assert download_button_disabled(body), "沒有可下載的結果時 MUST 停用"


def test_check_enables_download(env):
    """D1：跑完「檢查版本」後按鈕變亮、CSV 拿得到。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    d = client.post("/api/check").get_json()

    assert d["status"] == "no_update"
    assert d["export_ready"] is True
    resp = client.get("/api/export.csv")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    assert "text/csv" in resp.headers["Content-Type"]


def test_baseline_never_enables_download(env):
    """D1：「建立／更新基準」⛔ 不讓下載鈕亮 —— 含它自己的失敗路徑。"""
    client, _, mp = env
    stub_ok(mp)
    d = client.post("/api/baseline").get_json()
    assert d["status"] == "baseline_set"
    assert d["export_ready"] is False
    assert client.get("/api/export.csv").status_code == 409

    stub_fail(mp, iec.FetchError("連線逾時"))
    mp.setattr(main, "_throttle", {})
    err = client.post("/api/baseline").get_json()
    assert err["status"] == "error"
    assert err["export_ready"] is False, "建立基準失敗 ⛔ 不得誤點亮下載鈕"
    assert client.get("/api/export.csv").status_code == 409


def test_no_baseline_does_not_enable_download(env):
    """plan I4：沒有基準時按檢查 → 沒有可下載的結果。"""
    client, _, mp = env
    stub_ok(mp)
    d = client.post("/api/check").get_json()
    assert d["status"] == "no_baseline"
    assert d["export_ready"] is False
    assert client.get("/api/export.csv").status_code == 409


def test_index_clears_export(env):
    """D2（丙）：`GET /`（開頁 / 重整）清掉結果 → 按鈕變暗。

    ⚠️ 這代表 GET 帶副作用（HTTP 語意上 GET 應為安全）—— 是為了精確實現「丙」
    刻意付出的代價，Human 已知悉並記在 issue #3。本測試就是在守這個刻意行為。
    """
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    assert client.post("/api/check").get_json()["export_ready"] is True

    body = client.get("/").get_data(as_text=True)
    assert download_button_disabled(body), "重整後按鈕 MUST 變暗"
    assert client.get("/api/export.csv").status_code == 409


def test_panel_refresh_does_not_clear_export(env):
    """D2 / plan I2：帶 `X-Panel: 1` 的請求是「局部面板刷新」、不是重整 → ⛔ 不清除。

    回歸價值：前端在每次成功動作後都會呼叫 `refreshPanel()` 再打一次 `GET /`。
    若這裡被清掉，D1「檢查後按鈕變亮」根本無法成立。
    """
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    client.post("/api/check")

    body = client.get("/", headers={"X-Panel": "1"}).get_data(as_text=True)
    assert not download_button_disabled(body), "面板刷新後按鈕 MUST 仍然亮著"
    assert client.get("/api/export.csv").status_code == 200


def test_download_twice_in_same_page(env):
    """D2（丙）：下載動作 ⛔ 不清除 → 同一次頁面內可重複下載。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    client.post("/api/check")

    first = client.get("/api/export.csv")
    second = client.get("/api/export.csv")
    assert first.status_code == second.status_code == 200
    assert first.data == second.data


def test_download_does_not_hit_iec(env):
    """紅線：下載動作 ⛔ 不對 IEC 發任何請求（下載的是快照、不是重抓）。"""
    client, _, mp = env
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return HTML

    mp.setattr(iec, "fetch_html", counting)
    client.post("/api/baseline")
    client.post("/api/check")
    before = calls["n"]

    client.get("/api/export.csv")
    client.get("/api/export.csv")
    assert calls["n"] == before, "下載期間 ⛔ 不得再打 IEC"


def test_failed_check_is_still_exportable(env):
    """D3：檢查失敗仍要能下載，且「最新版次」欄寫失敗原因、⛔ 不留白。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")

    stub_fail(mp, iec.FetchError("連線逾時"))
    mp.setattr(main, "_throttle", {})
    d = client.post("/api/check").get_json()
    assert d["status"] == "error"
    assert d["export_ready"] is True, "D3：失敗也要輸出一列"

    text = client.get("/api/export.csv").data.decode("utf-8-sig")
    row = text.splitlines()[1]
    assert "連線逾時" in row, "D3：最新版次欄 MUST 寫失敗原因"
    assert "檢查失敗" in row
    assert sources.SOURCES[0]["name"] in row, "D5：失敗列照樣有名稱"
    assert sources.SOURCES[0]["url"] in row, "D5：失敗列照樣有連結"


def test_export_reflects_check_verdict(env):
    """UAT：「版次查詢結果」與網頁上顯示的結論一致。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")

    stub_ok(mp, HTML.replace('"edition":"4.0"', '"edition":"9.9"'))
    assert client.post("/api/check").get_json()["status"] == "updated"
    assert "有更新" in client.get("/api/export.csv").data.decode("utf-8-sig")


def test_target_name_is_shared_between_page_and_csv(env):
    """D5：名稱與連結只有**一份**定義 —— 頁面與 CSV 取自同一處。"""
    client, _, mp = env
    name = sources.SOURCES[0]["name"]
    url = sources.SOURCES[0]["url"]

    body = client.get("/").get_data(as_text=True)
    assert name in body and url in body

    stub_ok(mp)
    client.post("/api/baseline")
    client.post("/api/check")
    csv_text = client.get("/api/export.csv").data.decode("utf-8-sig")
    assert name in csv_text and url in csv_text

    # ⛔ 樣板裡不得再有一份寫死的名稱字面量（那就是第二份真相）
    template = (Path(main.__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
    assert name not in template, "D5：目標名稱 ⛔ 不得同時寫死在樣板裡"


def test_export_ready_is_not_stale_when_throttled(env):
    """plan I3：`export_ready` ⛔ 不得被節流快取 —— 快取的旗標會說謊。"""
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    assert client.post("/api/check").get_json()["export_ready"] is True

    client.get("/")   # 重整 → 匯出被清掉，但節流快取還在

    throttled = client.post("/api/check").get_json()
    assert throttled["throttled"] is True, "本測試的前提：這一次走的是節流快取"
    assert throttled["export_ready"] is False, "旗標 MUST 反映當下狀態、⛔ 不是 10 秒前的"


def test_export_does_not_write_any_file(env):
    """D2：匯出資料存記憶體、⛔ 完全不落檔。"""
    client, data_dir, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    client.post("/api/check")
    before = sorted(p.name for p in data_dir.iterdir())

    client.get("/api/export.csv")
    assert sorted(p.name for p in data_dir.iterdir()) == before, "匯出 ⛔ 不得產生任何檔案"
    assert before == ["baseline.json", "last_check.json"]


def test_baseline_does_not_clear_an_earned_export(env):
    """邊界釘樁：D1 只說「建立／更新基準 ⛔ 不讓按鈕亮」，**沒說要把已經有的結果清掉**。

    D2 明列的清除觸發只有 `GET /`。所以「檢查 → 按更新基準」之後，
    上一次的檢查結果快照 SHALL 仍可下載（它仍然是「最近一次檢查版本」的結果，沒有說謊）。
    """
    client, _, mp = env
    stub_ok(mp)
    client.post("/api/baseline")
    client.post("/api/check")
    before = client.get("/api/export.csv").data

    mp.setattr(main, "_throttle", {})
    ack = client.post("/api/baseline").get_json()
    assert ack["status"] == "baseline_set"
    assert ack["export_ready"] is True, "⛔ 不是它點亮的，但它也不該把別人點亮的弄暗"
    assert client.get("/api/export.csv").data == before
