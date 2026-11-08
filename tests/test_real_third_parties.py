import datetime as dt
import json
import random
from importlib import resources

from noisycompany import config, thirdparty
from noisycompany.engine import Engine

FAKE = {"www.example.org": [("cdn.example.net", 50), ("fonts.example.com", 120),
                            ("api.example.io", 900), ("video.example.tv", 6000)]}


def _patch(monkeypatch):
    monkeypatch.setattr(thirdparty, "_sites", lambda: FAKE)


def test_shipped_snapshot_is_valid_and_has_no_trackers():
    raw = json.loads(resources.files("noisycompany").joinpath("data/third_parties.json")
                     .read_text("utf-8"))
    assert raw["generated"] and raw["sites"]
    from noisycompany.web import TRACKER_FRAGMENTS
    for site, hosts in raw["sites"].items():
        assert 0 < len(hosts) <= 40
        times = [ms for _, ms in hosts]
        assert times == sorted(times)
        for host, _ in hosts:
            assert host != site and not any(f in host for f in TRACKER_FRAGMENTS)


def test_known_accepts_www_and_bare(monkeypatch):
    _patch(monkeypatch)
    assert thirdparty.known("example.org") == FAKE["www.example.org"]
    assert thirdparty.known("unknown.org") == []


def test_page_load_keeps_order_and_caps_gaps(monkeypatch):
    _patch(monkeypatch)
    plan = thirdparty.page_load("www.example.org", random.Random(1), keep=1.0, max_gap_s=2.5)
    assert [h for h, _ in plan] == [h for h, _ in FAKE["www.example.org"]]
    assert all(0 <= w <= 2.5 for _, w in plan)


def test_engine_replays_recorded_load(monkeypatch, tmp_path):
    _patch(monkeypatch)
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(2),
                 now=lambda: dt.datetime(2026, 3, 4, 20, 0))
    eng._sleep = lambda s: True
    seen = []
    eng.lookup = lambda host: (seen.append(host), (True, 300, "dns"))[1]
    assert not eng.real_page_load("www.example.org", "p")  # switch off
    eng.features.set("real_third_parties", True)
    assert eng.real_page_load("www.example.org", "p")
    assert seen and set(seen) <= {h for h, _ in FAKE["www.example.org"]}
    assert not eng.real_page_load("unknown.org", "p")
