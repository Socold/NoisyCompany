import random
import struct

from noisycompany import pcapstudy, study


def client_hello(sni: str, browser: bool) -> bytes:
    suites = ([0x1A1A] if browser else []) + list(range(0x1301, 0x1304)) + (
        list(range(0xC02B, 0xC033)) if browser else [0xC02F])
    exts = b""
    if browser:
        exts += struct.pack("!HH", 0x2A2A, 0)
    name = sni.encode()
    sn = struct.pack("!HBH", len(name) + 3, 0, len(name)) + name
    exts += struct.pack("!HH", 0, len(sn)) + sn
    if browser:
        alpn = b"\x00\x0c\x02h2\x08http/1.1"
        exts += struct.pack("!HH", 16, len(alpn)) + alpn
        for t in (5, 10, 11, 13, 18, 23, 27, 35, 43, 45, 51, 17513):
            exts += struct.pack("!HH", t, 2) + b"\x00\x00"
    body = (b"\x03\x03" + bytes(32) + b"\x00" + struct.pack("!H", 2 * len(suites))
            + b"".join(struct.pack("!H", s) for s in suites) + b"\x01\x00"
            + struct.pack("!H", len(exts)) + exts)
    hs = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def frame(src: int, sport: int, dport: int, payload: bytes) -> bytes:
    tcp = struct.pack("!HHIIBBHHH", sport, dport, 0, 0, 5 << 4, 0x18, 65535, 0, 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0,
                     bytes([192, 168, 1, src]), bytes([93, 184, 216, 34])) if dport == 443 \
        else struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0,
                         bytes([93, 184, 216, 34]), bytes([192, 168, 1, src]))
    return b"\x00" * 12 + b"\x08\x00" + ip + tcp


def write_pcap(packets) -> bytes:
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for ts, data in packets:
        out += struct.pack("<IIII", int(ts), int(ts % 1 * 1e6), len(data), len(data)) + data
    return out


def capture(n=40):
    rng = random.Random(0)
    packets, noise = [], []
    for i in range(n):
        ts, browser = 1_000_000 + i * 30.0, i % 2 == 0
        host = f"site{i}.example" if browser else f"decoy{i}.example"
        port = 40000 + i
        packets.append((ts, frame(2, port, 443, client_hello(host, browser))))
        for k in range(rng.randint(3, 30) if browser else rng.randint(1, 4)):
            packets.append((ts + 0.1 + k * 0.01, frame(2, 443, port, bytes(1400))))
        if not browser:
            noise.append(study.Event(ts + 0.5, host))
    return write_pcap(sorted(packets, key=lambda p: p[0])), noise


def test_parse_hello():
    h = pcapstudy.parse_hello(client_hello("lichess.org", True))
    assert h.sni == "lichess.org" and h.grease and h.alpn_h2 and h.extensions >= 10
    p = pcapstudy.parse_hello(client_hello("lichess.org", False))
    assert p.sni == "lichess.org" and not p.grease and p.ciphers == 4
    assert pcapstudy.parse_hello(b"\x17\x03\x03\x00\x01x") is None


def test_flows_labels_and_auc(tmp_path):
    data, noise = capture()
    fl = pcapstudy.flows(data)
    assert len(fl) == 40 and all(f.down for f in fl)
    xn, xh = pcapstudy.label_flows(data, noise)
    assert len(xn) == 20 and len(xh) == 20
    path = tmp_path / "c.pcap"
    path.write_bytes(data)
    res = pcapstudy.run(path, noise)
    assert res.auc > 0.9 and "grease" in res.weights


def test_rejects_garbage():
    import pytest
    with pytest.raises(pcapstudy.PcapError):
        list(pcapstudy._records(b"x" * 40))
