import datetime as dt
import random
import threading

import pytest

from noisycompany import config, impact
from noisycompany.budget import Budget
from noisycompany.engine import Engine
from noisycompany.netwatch import NetWatch, read_counters
from noisycompany.personas import PersonaRotator
from noisycompany.web import extract_links, host_allowed, is_blocked

PROC = """Inter-|   Receive                            |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets
    lo: 1000 0 0 0 0 0 0 0 1000 0 0 0 0 0 0 0
  eth0: {rx} 0 0 0 0 0 0 0 {tx} 0 0 0 0 0 0 0
docker0: 99999 0 0 0 0 0 0 0 99999 0 0 0 0 0 0 0
"""


def test_default_config_is_valid_for_every_preset():
    for preset in config.PRESETS:
        cfg = config.load(preset=preset)
        assert cfg["general"]["preset"] == preset
        assert config.load_personas(cfg)


def test_invalid_values_rejected(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[budget]\ndaily_mb = 0\n")
    with pytest.raises(config.ConfigError):
        config.load(bad)
    bad.write_text('[schedule]\nactive_hours = ["25:00-26:00"]\n')
    with pytest.raises(config.ConfigError):
        config.load(bad)


def test_time_range_across_midnight():
    tr = config.TimeRange.parse("22:00-02:00")
    assert tr.contains(23 * 60) and tr.contains(60) and not tr.contains(12 * 60)


def test_budget_caps_bytes_and_actions():
    now = [0.0]
    b = Budget(1000, 2, clock=lambda: now[0], today=lambda: dt.date(2026, 1, 1))
    assert b.can_act(900)
    b.record_bytes(900)
    assert not b.can_act(200)
    b.record_action()
    b.record_action()
    assert not b.can_act(0)
    assert b.seconds_until_action_slot() > 0
    now[0] = 3601
    assert b.can_act(0)


def test_budget_resets_daily():
    day = [dt.date(2026, 1, 1)]
    b = Budget(100, 10, today=lambda: day[0])
    b.record_bytes(100)
    assert b.remaining_bytes() == 0
    day[0] = dt.date(2026, 1, 2)
    assert b.remaining_bytes() == 100


def test_netwatch_ignores_virtual_ifaces_and_own_bytes():
    assert read_counters(PROC.format(rx=10, tx=5)) == 15
    t = [0.0]
    state = {"rx": 0}
    nw = NetWatch(8, reader=lambda: PROC.format(rx=state["rx"], tx=0), clock=lambda: t[0])
    nw.user_rate_bps()
    t[0], state["rx"] = 1.0, 5000
    nw.note_own_bytes(5000)  # all of it was ours
    assert nw.user_rate_bps() == 0
    t[0], state["rx"] = 2.0, 10000
    assert nw.user_rate_bps() == 5000  # 40 kbit/s > 8 kbit/s threshold


def test_link_extraction_and_filters():
    html = '<a href="/wiki/Tomato">x</a><a href="#top">t</a><a href="mailto:a@b">m</a>' \
        '<a href="https://ads.example/aclk?x">ad</a><a href="//en.wikipedia.org/wiki/Bee#s">b</a>'
    links = extract_links(html, "https://en.wikipedia.org/wiki/Gardening")
    assert "https://en.wikipedia.org/wiki/Tomato" in links
    assert "https://en.wikipedia.org/wiki/Bee" in links
    assert all(not link.startswith("mailto") for link in links)
    assert is_blocked("https://ads.example/aclk?x", ["/aclk"])
    assert host_allowed("https://fr.m.wikipedia.org/x", ["wikipedia.org"])
    assert not host_allowed("https://evilwikipedia.org/x", ["wikipedia.org"])


def test_persona_rotation_is_stable_within_epoch(tmp_path):
    personas = config.load_personas(config.load())
    t = [0.0]
    r = PersonaRotator(personas, 3, 1, tmp_path, clock=lambda: t[0])
    first = r.active()
    assert len(first) == 3
    t[0] = 3600
    assert r.active() == first
    again = PersonaRotator(personas, 3, 1, tmp_path, clock=lambda: t[0])
    assert again.active() == first  # salt persisted
    assert (tmp_path / "salt").stat().st_mode & 0o077 == 0


def test_estimate_balanced_is_light():
    est = impact.estimate(config.load())
    assert est.mb_per_day_expected <= 15
    assert est.avg_kbps_when_active < 5  # a few kbit/s at most
    eco = impact.estimate(config.load(preset="eco"))
    assert eco.mb_per_day_expected < est.mb_per_day_expected


def test_engine_dry_run_session_touches_no_network(monkeypatch):
    import noisycompany.dns
    import noisycompany.web

    def boom(*a, **k):
        raise AssertionError("network used in dry-run")

    monkeypatch.setattr(noisycompany.dns, "resolve", boom)
    monkeypatch.setattr(noisycompany.web.Fetcher, "fetch", boom)
    cfg = config.load()
    cfg["schedule"]["dwell_s"] = [0, 0]
    cfg["http"]["per_host_delay_s"] = 1
    eng = Engine(cfg, config.load_personas(cfg), None, dry_run=True, rng=random.Random(1),
                 stop=threading.Event())
    eng._sleep = lambda s: True
    for _ in range(20):
        eng.run_session()
    assert eng.stats.sessions == 20
    assert eng.stats.bytes > 0
    assert eng.stats.bytes <= cfg["budget"]["daily_mb"] * 1_000_000


def test_engine_respects_active_hours():
    cfg = config.load()
    cfg["schedule"]["active_hours"] = ["10:00-11:00"]
    eng = Engine(cfg, config.load_personas(cfg), None, dry_run=True,
                 now=lambda: dt.datetime(2026, 1, 1, 3, 0))
    assert not eng.is_active_time()


def test_engine_paces_budget_over_the_day():
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), None, dry_run=True,
                 now=lambda: dt.datetime(2026, 1, 1, 8, 0))
    eng.budget.record_bytes(int(cfg["budget"]["daily_mb"] * 1_000_000 * 0.5))
    assert eng.ahead_of_pace()  # half the budget spent 30 min into the day


def test_dns_candidates_never_invent_subdomains():
    from noisycompany.dns import candidate_hosts
    rng = random.Random(0)
    for _ in range(50):
        assert candidate_hosts(["fr.wikipedia.org"], rng) == "fr.wikipedia.org"
        assert candidate_hosts(["lpo.fr"], rng) in ("lpo.fr", "www.lpo.fr")
        assert candidate_hosts(["www.lpo.fr"], rng) in ("lpo.fr", "www.lpo.fr")


def test_estimate_accounts_for_doh_cost():
    cfg = config.load(preset="eco")
    base = impact.estimate(cfg).mb_per_day_expected
    cfg["features"]["doh_sink"] = True
    assert impact.estimate(cfg).mb_per_day_expected > base
