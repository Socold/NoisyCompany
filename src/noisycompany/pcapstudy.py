"""Separability study on packets: sizes, timing and TLS ClientHello shape.

`noisycompany study --pcap capture.pcap --noise labelled.jsonl` reads a capture taken on
your own network (tcpdump -w or Wireshark, pcap or pcapng), groups TCP packets to port
443 into flows, and labels a flow as noise when its TLS server name (SNI) is a host that
NoisyCompany fetched within a few seconds of the flow start. Everything else is your real
traffic. Each flow becomes a vector of what an on-path observer sees without decrypting:
packet counts and sizes both ways, duration, and the ClientHello's shape (length, number
of cipher suites and extensions, GREASE, ALPN). The same cross-validated logistic
regression as the DNS study scores it by ROC AUC.

Expect a high AUC: NoisyCompany speaks TLS through Python's ssl module, whose ClientHello
does not look like a browser's (no GREASE, fewer extensions). That is the measured limit
of daemon-side web noise; the browser companion, which uses the browser's own TLS stack,
does not have it. Stdlib only, nothing leaves the machine.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from noisycompany import study

FEATURES = [
    "pkts_up", "pkts_down", "bytes_up", "bytes_down", "mean_up", "mean_down",
    "duration", "hello_len", "ciphers", "extensions", "grease", "alpn_h2",
]
MATCH_S = 5.0


class PcapError(ValueError):
    pass


@dataclass
class Flow:
    start: float
    client: tuple[bytes, int]
    end: float = 0.0
    up: list[int] = field(default_factory=list)
    down: list[int] = field(default_factory=list)
    hello: bytearray = field(default_factory=bytearray)


@dataclass
class Hello:
    sni: str = ""
    length: int = 0
    ciphers: int = 0
    extensions: int = 0
    grease: bool = False
    alpn_h2: bool = False


# ------------------------------------------------------------------ capture files
def _records(data: bytes) -> Iterator[tuple[float, int, bytes]]:
    """(timestamp, link type, frame) from a pcap or pcapng file."""
    if len(data) < 24:
        raise PcapError("file too short")
    magic = data[:4]
    if magic == b"\x0a\x0d\x0d\x0a":
        yield from _pcapng(data)
        return
    for endian, scale in (("<", 1e-6), (">", 1e-6)):
        m = struct.unpack(endian + "I", magic)[0]
        if m in (0xA1B2C3D4, 0xA1B23C4D):
            scale = 1e-9 if m == 0xA1B23C4D else 1e-6
            link = struct.unpack(endian + "I", data[20:24])[0] & 0xFFFF
            off = 24
            while off + 16 <= len(data):
                sec, frac, incl, _ = struct.unpack(endian + "IIII", data[off:off + 16])
                off += 16
                yield sec + frac * scale, link, data[off:off + incl]
                off += incl
            return
    raise PcapError("not a pcap or pcapng file")


def _pcapng(data: bytes) -> Iterator[tuple[float, int, bytes]]:
    off, endian, links = 0, "<", []
    while off + 12 <= len(data):
        btype = struct.unpack(endian + "I", data[off:off + 4])[0]
        if btype == 0x0A0D0D0A:  # section header: byte order magic
            endian = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            links = []
        blen = struct.unpack(endian + "I", data[off + 4:off + 8])[0]
        if blen < 12 or off + blen > len(data):
            break
        body = data[off + 8:off + blen - 4]
        if btype == 1:  # interface description
            links.append(struct.unpack(endian + "H", body[:2])[0])
        elif btype == 6 and len(body) >= 20:  # enhanced packet
            iface, hi, lo, cap, _ = struct.unpack(endian + "IIIII", body[:20])
            link = links[iface] if iface < len(links) else 1
            yield ((hi << 32) | lo) * 1e-6, link, body[20:20 + cap]
        off += blen


def _ip_payload(link: int, frame: bytes) -> bytes | None:
    if link == 1:  # Ethernet, with optional VLAN tags
        off, etype = 14, struct.unpack("!H", frame[12:14])[0] if len(frame) >= 14 else 0
        while etype in (0x8100, 0x88A8) and len(frame) >= off + 4:
            etype = struct.unpack("!H", frame[off + 2:off + 4])[0]
            off += 4
        return frame[off:] if etype in (0x0800, 0x86DD) else None
    if link == 113:  # Linux cooked
        return frame[16:]
    if link == 276:  # Linux cooked v2
        return frame[20:]
    if link in (101, 228, 229):  # raw IP
        return frame
    return None


def _tcp(ip: bytes) -> tuple[bytes, bytes, int, int, bytes] | None:
    """(src, dst, sport, dport, payload) of a TCP segment, or None."""
    if not ip:
        return None
    version = ip[0] >> 4
    if version == 4 and len(ip) >= 20 and ip[9] == 6:
        ihl = (ip[0] & 15) * 4
        total = struct.unpack("!H", ip[2:4])[0] or len(ip)
        src, dst, seg = ip[12:16], ip[16:20], ip[ihl:total]
    elif version == 6 and len(ip) >= 40 and ip[6] == 6:
        src, dst, seg = ip[8:24], ip[24:40], ip[40:40 + struct.unpack("!H", ip[4:6])[0]]
    else:
        return None
    if len(seg) < 20:
        return None
    sport, dport = struct.unpack("!HH", seg[:4])
    return src, dst, sport, dport, seg[(seg[12] >> 4) * 4:]


def flows(data: bytes, port: int = 443) -> list[Flow]:
    table: dict[tuple[bytes, int, bytes], Flow] = {}
    for ts, link, frame in _records(data):
        seg = _tcp(_ip_payload(link, frame) or b"")
        if not seg:
            continue
        src, dst, sport, dport, payload = seg
        if dport == port:
            key, up = (src, sport, dst), True
        elif sport == port:
            key, up = (dst, dport, src), False
        else:
            continue
        flow = table.get(key)
        if flow is None:
            flow = table[key] = Flow(ts, (src, sport))
        flow.end = ts
        if not payload:
            continue
        (flow.up if up else flow.down).append(len(payload))
        if up and len(flow.hello) < 16384 and not flow.down:
            flow.hello += payload
    return sorted(table.values(), key=lambda f: f.start)


# ------------------------------------------------------------------ TLS ClientHello
def _is_grease(v: int) -> bool:
    return v & 0x0F0F == 0x0A0A and v >> 8 == v & 0xFF


def parse_hello(raw: bytes) -> Hello | None:
    """Parse a TLS ClientHello from the start of a client stream (no decryption)."""
    try:
        if raw[0] != 0x16 or raw[5] != 0x01:
            return None
        rec_len = struct.unpack("!H", raw[3:5])[0]
        h = raw[9:5 + rec_len]
        off = 2 + 32
        off += 1 + h[off]  # session id
        n = struct.unpack("!H", h[off:off + 2])[0]
        suites = [struct.unpack("!H", h[off + 2 + i:off + 4 + i])[0] for i in range(0, n, 2)]
        off += 2 + n
        off += 1 + h[off]  # compression methods
        end = off + 2 + struct.unpack("!H", h[off:off + 2])[0]
        off += 2
        out = Hello(length=rec_len, ciphers=sum(not _is_grease(s) for s in suites),
                    grease=any(_is_grease(s) for s in suites))
        while off + 4 <= end:
            etype, elen = struct.unpack("!HH", h[off:off + 4])
            body = h[off + 4:off + 4 + elen]
            off += 4 + elen
            if _is_grease(etype):
                out.grease = True
                continue
            out.extensions += 1
            if etype == 0 and len(body) > 5:  # server_name
                name_len = struct.unpack("!H", body[3:5])[0]
                out.sni = body[5:5 + name_len].decode("ascii", "replace").lower()
            elif etype == 16:  # ALPN
                out.alpn_h2 = b"\x02h2" in body
        return out
    except (IndexError, struct.error):
        return None


# ------------------------------------------------------------------ study
def featurize(flow: Flow, hello: Hello) -> list[float]:
    up, down = flow.up or [0], flow.down or [0]
    return [
        math.log1p(len(flow.up)), math.log1p(len(flow.down)),
        math.log1p(sum(up)), math.log1p(sum(down)),
        math.log1p(sum(up) / len(up)), math.log1p(sum(down) / len(down)),
        math.log1p(flow.end - flow.start), math.log1p(hello.length),
        float(hello.ciphers), float(hello.extensions), float(hello.grease),
        float(hello.alpn_h2),
    ]


def label_flows(data: bytes, noise: list[study.Event]) -> tuple[list[list[float]],
                                                                 list[list[float]]]:
    by_host: dict[str, list[float]] = {}
    for e in noise:
        by_host.setdefault(e.host, []).append(e.ts)
    xn, xh = [], []
    for flow in flows(data):
        hello = parse_hello(bytes(flow.hello))
        if hello is None or not hello.sni:
            continue
        times = by_host.get(hello.sni, [])
        is_noise = any(abs(t - flow.start) <= MATCH_S for t in times)
        (xn if is_noise else xh).append(featurize(flow, hello))
    return xn, xh


def run(pcap: Path, noise: list[study.Event], folds: int = 5,
        seed: int = 0) -> study.StudyResult:
    xn, xh = label_flows(pcap.read_bytes(), noise)
    return study.cross_validate(xn, xh, FEATURES, folds, seed)
