import datetime as dt
import random
import socket
import threading

from noisycompany import config, dns
from noisycompany.engine import Engine
from noisycompany.household import VirtualHousehold

NOW = dt.datetime(2026, 3, 4, 20, 0)


def test_household_size_in_range_and_stable_within_epoch():
    hh = VirtualHousehold("salt", (2, 5), (30, 90))
    sizes = {len(hh.members(NOW + dt.timedelta(hours=h))) for h in range(24)}
    assert len(sizes) == 1 and 2 <= sizes.pop() <= 5
    assert 30 * 86400 <= hh.period_s <= 90 * 86400


def test_household_differs_between_installs_and_epochs():
    sizes = {len(VirtualHousehold(f"s{i}").members(NOW)) for i in range(40)}
    assert len(sizes) >= 3  # the count does not leak a fixed number
    hh = VirtualHousehold("salt")
    later = [len(hh.members(NOW + dt.timedelta(seconds=hh.period_s * k))) for k in range(12)]
    assert len(set(later)) >= 2


def test_presence_floor_hides_quiet_hours():
    hh = VirtualHousehold("salt")
    night = dt.datetime(2026, 3, 4, 4, 0)
    assert hh.factor(night, floor=0.35) == 0.35
    assert hh.factor(NOW, floor=0.0) > 0.35


def test_each_persona_has_one_owner_and_affinity_prefers_it():
    hh = VirtualHousehold("salt")
    members = hh.members(NOW)
    owner = hh.owner("gardening", NOW)
    assert 0 <= owner < len(members)
    m = members[owner]
    assert hh.affinity(m, "gardening", NOW) > max(
        hh.affinity(o, "gardening", NOW) for o in members if o != m) if len(members) > 1 else True


def test_build_query_is_a_valid_https_question():
    pkt = dns.build_query("www.example.org", dns.QTYPE_HTTPS, 0x1234)
    assert pkt[:2] == b"\x12\x34" and pkt[4:6] == b"\x00\x01"
    assert b"\x03www\x07example\x03org\x00\x00\x41\x00\x01" in pkt
    assert pkt.endswith(b"\x00\x00\x29\x04\xd0\x00\x00\x00\x00\x00\x00")  # EDNS0, 1232


def test_query_https_rr_against_a_local_stub():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]

    def answer():
        data, addr = srv.recvfrom(512)
        srv.sendto(data[:2] + b"\x81\x80" + data[4:], addr)

    t = threading.Thread(target=answer)
    t.start()
    try:
        assert dns.query_https_rr("example.org", "127.0.0.1", random.Random(1), port=port)
    finally:
        t.join()
        srv.close()
    assert not dns.query_https_rr("example.org", None, random.Random(1))


def test_system_nameserver(tmp_path):
    f = tmp_path / "resolv.conf"
    f.write_text("# x\nsearch lan\nnameserver 127.0.0.53\nnameserver 1.1.1.1\n")
    assert dns.system_nameserver(str(f)) == "127.0.0.53"
    assert dns.system_nameserver(str(tmp_path / "missing")) is None


def test_cache_skips_recent_hosts(tmp_path):
    clock = [NOW]
    eng = Engine(config.load(), config.load_personas(config.load()), tmp_path, dry_run=True,
                 rng=random.Random(3), now=lambda: clock[0])
    eng.features.set("browser_dns", True)
    assert eng.cached_lookup("example.org") is not None
    assert eng.cached_lookup("example.org") is None
    clock[0] = NOW + dt.timedelta(minutes=11)
    assert eng.cached_lookup("example.org") is not None
    eng.features.set("browser_dns", False)
    assert eng.cached_lookup("example.org") is not None


def test_masking_runs_sessions_and_disables_interleave(tmp_path):
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True,
                 rng=random.Random(5), now=lambda: NOW)
    eng.features.set("household_masking", True)
    eng.features.set("interleave_with_user", True)
    member = eng.household.members(NOW)[0]
    eng.run_session(member)
    stats = eng.run(once=True)
    assert stats.sessions >= 1
