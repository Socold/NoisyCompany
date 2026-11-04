import http.client
import json
import random
import struct
import threading
import time

import pytest

from noisycompany import config, doh
from noisycompany.engine import Engine
from noisycompany.features import FEATURES, FeatureSet, NotAvailable, UnknownFeature
from noisycompany.metered import MeteredProbe, parse_nmcli
from noisycompany.personas import PersonaRotator
from noisycompany.server import render_metrics


def make_engine(tmp_path, **kw):
    cfg = config.load()
    cfg["schedule"]["dwell_s"] = [0, 0]
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True,
                 rng=random.Random(3), stop=threading.Event(), **kw)
    eng._sleep = lambda s: True
    return eng


def test_every_roadmap_item_has_a_switch_off_by_default(tmp_path):
    fs = FeatureSet(config.load(), tmp_path)
    assert len(FEATURES) >= 15
    assert not any(f["enabled"] for f in fs.snapshot())


def test_switch_persists_and_planned_items_refuse(tmp_path):
    fs = FeatureSet(config.load(), tmp_path)
    fs.set("doh_sink", True)
    assert FeatureSet(config.load(), tmp_path).enabled("doh_sink")
    with pytest.raises(NotAvailable):
        fs.set("test_planned", True)
    with pytest.raises(UnknownFeature):
        fs.set("nope", True)
    fs.set("test_planned", False)  # switching a planned item off is harmless


def test_switch_from_another_process_is_seen_on_reload(tmp_path):
    a, b = FeatureSet(config.load(), tmp_path), FeatureSet(config.load(), tmp_path)
    time.sleep(0.01)
    a.set("metrics", True)
    b.reload()
    assert b.enabled("metrics")


def test_persona_drift_keeps_main_hobby_across_rotations(tmp_path):
    personas = config.load_personas(config.load())
    t = [0.0]
    r = PersonaRotator(personas, 3, 1, tmp_path, clock=lambda: t[0])
    mains, sets = set(), set()
    for day in range(30):
        t[0] = day * 86400 + 10
        act = r.active(drift_main_days=1000)
        mains.add(act[0])
        sets.add(tuple(act[1:]))
        assert act[0] not in act[1:]
    assert len(mains) == 1 and len(sets) > 1


def test_locale_pack_fr_loads_and_is_used(tmp_path):
    eng = make_engine(tmp_path)
    eng.features.set("locale_packs", True)
    eng.features.set("labelled_log", True)
    eng.cfg["dns"]["weight"] = 0.0001
    for _ in range(30):
        eng.run_session()
    recs = [json.loads(x) for x in (tmp_path / "labelled.jsonl").read_text().splitlines()]
    assert any("fr.wikipedia.org" in r["target"] for r in recs)
    assert all(r["label"] == "benign-noise" for r in recs)


def test_metered_guard_switches_to_eco_cap(tmp_path):
    eng = make_engine(tmp_path, metered_probe=MeteredProbe(runner=lambda: "GENERAL.METERED:yes"))
    eng.dry_run = False  # probe is fake, no network is touched by refresh_features
    eng.features.set("metered_guard", True)
    eng.refresh_features()
    assert eng.metered and eng.budget.daily_bytes == eng.eco_cap < eng.base_cap
    eng.features.set("metered_guard", False)
    eng.refresh_features()
    assert eng.budget.daily_bytes == eng.base_cap


def test_parse_nmcli():
    assert parse_nmcli("GENERAL.METERED:no\nGENERAL.METERED:yes (guessed)\n")
    assert not parse_nmcli("GENERAL.METERED:no (guessed)\nGENERAL.METERED:unknown\n")


def test_doh_query_wire_format():
    q = doh.build_query("en.wikipedia.org", "AAAA")
    qid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", q[:12])
    assert (qid, flags, qd, an) == (0, 0x0100, 1, 0)
    assert q[12:] == b"\x02en\x09wikipedia\x03org\x00" + struct.pack("!HH", 28, 1)
    with pytest.raises(ValueError):
        doh.build_query("a" * 70 + ".com")


def test_metrics_text(tmp_path):
    text = render_metrics(make_engine(tmp_path).status())
    assert "# TYPE noisycompany_bytes_total counter" in text
    assert 'noisycompany_pages_total{result="ok"} 0' in text


def _req(port, method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read(), r.headers


def test_dashboard_buttons_and_hardening(tmp_path):
    eng = make_engine(tmp_path)
    eng.options["dashboard_port"] = 0
    from noisycompany.server import LocalServer
    srv = LocalServer(0, eng, "dashboard")
    srv.start()
    try:
        port = srv.address[1]
        host = {"Host": f"127.0.0.1:{port}"}
        status, page, hdrs = _req(port, "GET", "/", host)
        assert status == 200 and "script-src 'self'" in hdrs["Content-Security-Policy"]
        token = page.decode().split('name="nc-token" content="')[1].split('"')[0]
        # DNS rebinding: foreign Host header rejected
        assert _req(port, "GET", "/api/status", {"Host": "evil.example"})[0] == 421
        post = {"Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}",
                "Content-Type": "application/json"}
        body = json.dumps({"on": True})
        # no token / cross-origin -> refused
        assert _req(port, "POST", "/api/features/metrics", post, body)[0] == 403
        assert _req(port, "POST", "/api/features/metrics",
                    post | {"X-NC-Token": token, "Origin": "http://evil.example"}, body)[0] == 403
        ok = _req(port, "POST", "/api/features/metrics", post | {"X-NC-Token": token}, body)
        assert ok[0] == 200 and eng.features.enabled("metrics")
        planned = _req(port, "POST", "/api/features/test_planned",
                       post | {"X-NC-Token": token}, body)
        assert planned[0] == 409
        status, data, _ = _req(port, "GET", "/api/status", host)
        snap = {f["id"]: f for f in json.loads(data)["features"]}
        assert snap["metrics"]["enabled"] and not snap["test_planned"]["available"]
    finally:
        srv.stop()


def test_feature_ids_are_unique():
    from noisycompany import features
    ids = [f.id for f in features.FEATURES]
    assert len(ids) == len(set(ids))


def test_dashboard_has_a_french_title_for_every_feature():
    from importlib import resources
    js = resources.files("noisycompany.data").joinpath("dashboard.js").read_text("utf-8")
    block = js[js.index("const FR_FEATURES"):js.index("};", js.index("const FR_FEATURES"))]
    missing = [f.id for f in FEATURES if f"  {f.id}: [" not in block]
    assert not missing
    from noisycompany import privacy
    checks = privacy.build_report(__import__("pathlib").Path("/nonexistent"), {}).checks
    assert all(f"  {c.id}: [" in js for c in checks)
