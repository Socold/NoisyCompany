import datetime as dt
import json

from test_features import make_engine

from noisycompany import config, impact, rhythm
from noisycompany.web import third_party_hosts

PAGE = """<html><head>
<script src="https://www.googletagmanager.com/gtm.js"></script>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">
<link rel="preconnect" href="https://upload.wikimedia.org">
<script src="/static/app.js"></script><script src="https://cdn.jsdelivr.net/x.js"></script>
</head><body><img src="https://pixel.example-ads.com/p.gif">
<img src="https://img.chess.com/a.png"><img src="https://93.184.216.34/x.png">
<a href="https://other.org/">not an embed</a></body></html>"""


def test_third_party_hosts_skip_first_party_trackers_and_literals():
    hosts = third_party_hosts(PAGE, "https://www.chess.com/openings")
    assert hosts == ["fonts.googleapis.com", "upload.wikimedia.org", "cdn.jsdelivr.net"]


def test_rhythm_weekend_later_mornings_and_evening_peak():
    tue_8 = dt.datetime(2026, 11, 3, 8, 0)
    sun_8 = dt.datetime(2026, 11, 8, 8, 0)
    tue_20 = dt.datetime(2026, 11, 3, 20, 0)
    assert rhythm.factor(sun_8) < rhythm.factor(tue_8) < rhythm.factor(tue_20)
    assert rhythm.day_off(dt.date(2026, 12, 25)) and not rhythm.day_off(dt.date(2026, 12, 23))
    assert rhythm.factor(dt.datetime(2026, 11, 3, 3, 0)) == 0
    assert rhythm.session_gap(600, tue_20) < 600 < rhythm.session_gap(600, sun_8)
    assert rhythm.factor(dt.datetime(2026, 8, 4, 20)) < rhythm.factor(tue_20)


def test_dns_coherence_reuses_hosts_seen_while_reading(tmp_path):
    eng = make_engine(tmp_path)
    eng.features.set("dns_coherence", True)
    eng.features.set("labelled_log", True)
    eng.remember_hosts("chess", ["https://www.chessgames.com/a", "https://lichess.org/b"])
    eng.cfg["dns"]["lookups_per_session"] = [30, 30]
    eng.dns_session(["en.wikipedia.org"], "chess")
    log = (tmp_path / "labelled.jsonl").read_text().splitlines()
    targets = [json.loads(x)["target"] for x in log]
    assert {"www.chessgames.com", "lichess.org"} <= set(targets)
    assert "en.wikipedia.org" in targets  # still some fresh lookups


def test_seen_hosts_are_bounded(tmp_path):
    eng = make_engine(tmp_path)
    eng.remember_hosts("p", [f"https://h{i}.example/" for i in range(200)])
    assert len(eng.seen_hosts["p"]) == 50 and eng.seen_hosts["p"][-1] == "h199.example"


def test_third_party_burst_is_dns_only_and_labelled(tmp_path):
    eng = make_engine(tmp_path)
    eng.features.set("labelled_log", True)
    eng.third_party_burst(PAGE, "https://www.chess.com/openings", "chess")
    recs = [json.loads(x) for x in (tmp_path / "labelled.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in recs] == ["dns-third-party"] * 3
    assert all(r["bytes"] <= 5_000 for r in recs)


def test_estimate_counts_third_party_lookups():
    cfg = config.load()
    base = impact.estimate(cfg).dns_lookups_per_day
    cfg["features"]["third_party_bursts"] = True
    assert impact.estimate(cfg).dns_lookups_per_day > base


def test_study_reads_pihole_ftl_db_and_adguard_querylog(tmp_path):
    import sqlite3
    import time

    from noisycompany import study
    db = tmp_path / "pihole-FTL.db"
    now = int(time.time())
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE queries (id INTEGER, timestamp INTEGER, domain TEXT)")
        c.executemany("INSERT INTO queries VALUES (?, ?, ?)",
                      [(1, now - 60, "Example.ORG."), (2, now - 30, "www.wikipedia.org")])
    assert [e.host for e in study.load_trace(db)] == ["example.org", "www.wikipedia.org"]
    log = tmp_path / "querylog.json"
    log.write_text('{"T":"2026-11-03T20:01:02.5+01:00","QH":"lichess.org","QT":"A"}\n')
    assert study.load_trace(log)[0].host == "lichess.org"


def test_grafana_dashboard_only_uses_exported_metrics():
    import re
    from pathlib import Path

    from noisycompany.server import render_metrics
    status = {"stats": {k: 1 for k in ("sessions", "dns_ok", "dns_fail", "pages_ok",
                                       "pages_fail", "robots_denied", "bytes", "paused_busy",
                                       "paused_budget")},
              "bytes_today": 1, "daily_cap_bytes": 2, "metered": False}
    exported = set(re.findall(r"^(noisycompany_\w+)", render_metrics(status), re.M))
    dash = json.loads(Path("deploy/grafana/noisycompany-dashboard.json").read_text())
    used = {m for p in dash["panels"] for t in p["targets"]
            for m in re.findall(r"noisycompany_\w+", t["expr"])}
    assert used and used <= exported
