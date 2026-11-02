import gzip
import http.client
import json
import os
import socket
import stat
import zlib

import pytest

from noisycompany import config, web
from noisycompany.cli import main
from noisycompany.engine import accept_language
from noisycompany.web import Fetcher, _decode, is_public_host


@pytest.fixture(autouse=True)
def clear_cache():
    web._PUBLIC_CACHE.clear()


def fake_resolver(table):
    def resolve(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in table[host]]
    return resolve


@pytest.mark.parametrize("ip", ["127.0.0.1", "192.168.1.1", "10.0.0.8", "172.16.3.4",
                                "169.254.169.254", "100.64.0.1", "::1", "fd00::1", "0.0.0.0"])  # noqa: S104
def test_private_and_special_addresses_are_refused(ip):
    assert not is_public_host("x.example", resolver=fake_resolver({"x.example": [ip]}))


def test_rebinding_mixed_answer_is_refused():
    r = fake_resolver({"mixed.example": ["93.184.216.34", "192.168.1.1"]})
    assert not is_public_host("mixed.example", resolver=r)
    web._PUBLIC_CACHE.clear()
    assert is_public_host("ok.example", resolver=fake_resolver({"ok.example": ["93.184.216.34"]}))


def test_literal_ips_and_bad_schemes(monkeypatch):
    f = Fetcher("UA", 5, 1000)
    assert not f.url_allowed("http://192.168.1.1/admin")
    assert not f.url_allowed("http://[::1]:8123/")
    assert not f.url_allowed("file:///etc/passwd")
    assert not f.url_allowed("ftp://example.org/")
    monkeypatch.setattr(web, "is_public_host", lambda h: True)
    f.scope = ["en.wikipedia.org"]
    assert f.url_allowed("https://en.wikipedia.org/wiki/X")
    assert not f.url_allowed("https://evil.example/")


def test_redirect_out_of_scope_is_not_followed(monkeypatch):
    monkeypatch.setattr(web, "is_public_host", lambda h: True)
    f = Fetcher("UA", 5, 1000)
    f.scope = ["en.wikipedia.org"]
    handler = web._ScopedRedirects(f)
    req = web.urllib.request.Request("https://en.wikipedia.org/a")
    assert handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/") is None
    assert handler.redirect_request(req, None, 302, "Found", {}, "http://192.168.1.1/") is None
    ok = handler.redirect_request(req, None, 302, "Found", {}, "https://en.wikipedia.org/b")
    assert ok is not None


def test_gzip_bomb_is_capped():
    bomb = gzip.compress(b"A" * 50_000_000)
    assert len(bomb) < 200_000
    assert len(_decode(bomb, "gzip", "utf-8")) <= web.MAX_DECODED_BYTES
    deflated = zlib.compress(b"B" * 50_000_000)
    assert len(_decode(deflated, "deflate", "utf-8")) <= web.MAX_DECODED_BYTES


def test_unknown_charset_does_not_crash():
    assert _decode("héllo".encode(), "", "x-made-up-charset") == "héllo"


def test_doh_url_must_be_https(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[features.options]\ndoh_url = "http://dns.example/dns-query"\n')
    with pytest.raises(config.ConfigError):
        config.load(p)


def test_accept_language_matches_persona():
    assert accept_language(["fr.wikipedia.org", "www.lpo.fr"]).startswith("fr-FR")
    assert accept_language(["en.wikipedia.org"]).startswith("en-US")


def test_state_files_are_private(tmp_path):
    state = tmp_path / "state"
    old = os.umask(0o022)
    try:
        assert main(["features", "on", "metrics", "--state-dir", str(state)]) == 0
        assert main(["collective", "create", "--personas", "chess,jazz", "--join",
                     "--state-dir", str(state)]) == 0
    finally:
        os.umask(old)
    for path in [state, *state.iterdir()]:
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, path


def test_dashboard_negative_content_length(tmp_path):
    import random
    import threading

    from noisycompany.engine import Engine
    from noisycompany.server import LocalServer
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(0),
                 stop=threading.Event())
    srv = LocalServer(0, eng, "dashboard")
    srv.start()
    try:
        port = srv.address[1]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
        token = c.getresponse().read().decode().split('nc-token" content="')[1].split('"')[0]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.putrequest("POST", "/api/features/metrics", skip_host=True)
        for k, v in {"Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}",
                     "X-NC-Token": token, "Content-Length": "-1"}.items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()  # must answer (400), not hang reading to EOF
        assert r.status == 400
        assert json.loads(r.read())["error"]
    finally:
        srv.stop()


def test_labelled_log_is_rotated(tmp_path):
    import random
    import threading

    from noisycompany.engine import Engine
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(0),
                 stop=threading.Event())
    eng.features.set("labelled_log", True)
    (tmp_path / "labelled.jsonl").write_bytes(b"x" * 10_000_001)
    eng.label("dns", "example.org", True, 300, "chess")
    assert (tmp_path / "labelled.jsonl.1").stat().st_size == 10_000_001
    assert (tmp_path / "labelled.jsonl").stat().st_size < 1000


def test_connection_is_pinned_to_the_vetted_address(monkeypatch):
    # The check resolved a public address; a later rebinding to the LAN must not matter.
    web._PUBLIC_CACHE["pinned.example"] = (web.time.monotonic(), ("93.184.216.34",))
    seen = []
    monkeypatch.setattr(web.socket, "create_connection",
                        lambda addr, *a, **k: seen.append(addr) or object())
    conn = web._PinnedHTTPConnection("pinned.example", 80)
    conn.connect()
    assert seen == [("93.184.216.34", 80)]


def test_pinned_connection_refuses_private_hosts(monkeypatch):
    web._PUBLIC_CACHE["lan.example"] = (web.time.monotonic(), ())
    monkeypatch.setattr(web.socket, "create_connection",
                        lambda *a, **k: pytest.fail("must not connect"))
    with pytest.raises(OSError):
        web._PinnedHTTPConnection("lan.example", 80).connect()


def test_opener_pins_unless_a_proxy_is_set(monkeypatch):
    monkeypatch.setattr(web.urllib.request, "getproxies", lambda: {})
    f = Fetcher("UA", 5, 1000)
    f._opener = None
    handlers = []
    monkeypatch.setattr(web.urllib.request, "build_opener", lambda *h: handlers.extend(h) or h)
    try:
        f._open(web.urllib.request.Request("https://example.org/"))
    except AttributeError:
        pass
    assert any(isinstance(h, web._PinnedHTTPSHandler) for h in handlers)
