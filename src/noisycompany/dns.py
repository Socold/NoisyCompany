"""DNS noise: resolve persona-coherent hostnames through the system resolver.

Using the system resolver (not a hard-coded server) is deliberate: the goal is to add
noise exactly where the user's real queries go (ISP resolver, router, DoH stub...).
A lookup costs roughly 100-300 bytes on the wire and no TCP connection.
"""

from __future__ import annotations

import logging
import random
import socket

log = logging.getLogger(__name__)

# Rough on-the-wire size of one A+AAAA query/answer pair, used for budgeting.
DNS_BYTES_ESTIMATE = 300



def candidate_hosts(domains: list[str], rng: random.Random) -> str:
    """Pick a hostname that really exists: the persona domain, or www./bare variant.

    Invented subdomains (cdn., api.) mostly return NXDOMAIN, which is cheap for an
    observer to spot as synthetic.
    """
    domain = rng.choice(domains).lower().rstrip(".")
    parts = domain.split(".")
    if len(parts) == 2:
        return rng.choice([domain, "www." + domain])
    if parts[0] == "www":
        return rng.choice([domain, ".".join(parts[1:])])
    return domain


def resolve(host: str, timeout: float = 4.0) -> bool:
    """Resolve host; return True on success. Never raises."""
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True
    except (OSError, UnicodeError) as exc:
        log.debug("dns %s failed: %s", host, exc)
        return False
    finally:
        socket.setdefaulttimeout(previous)


# ------------------------------------------------------------ browser-like DNS (browser_dns)
# Current browsers ask for an HTTPS record (type 65, RFC 9460) next to A/AAAA for every
# site they open. getaddrinfo() never does, which makes daemon lookups easy to tell apart.
HTTPS_RR_BYTES_ESTIMATE = 160
QTYPE_HTTPS = 65


def system_nameserver(path: str = "/etc/resolv.conf") -> str | None:
    """First nameserver of resolv.conf (the system stub, e.g. 127.0.0.53), or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1].split("%")[0]
    except OSError:
        pass
    return None


def build_query(host: str, qtype: int, txid: int) -> bytes:
    """Minimal DNS query packet (recursion desired, one question, EDNS0 like a stub)."""
    labels = host.rstrip(".").encode("idna").split(b".")
    if not labels or any(not 0 < len(label) < 64 for label in labels):
        raise ValueError(f"bad hostname {host!r}")
    qname = b"".join(bytes([len(label)]) + label for label in labels) + b"\0"
    header = txid.to_bytes(2, "big") + b"\x01\x00" + b"\x00\x01\x00\x00\x00\x00\x00\x01"
    opt = b"\x00" + b"\x00\x29" + (1232).to_bytes(2, "big") + b"\x00\x00\x00\x00" + b"\x00\x00"
    return header + qname + qtype.to_bytes(2, "big") + b"\x00\x01" + opt


def query_https_rr(host: str, server: str | None, rng: random.Random,
                   timeout: float = 3.0, port: int = 53) -> bool:
    """Send one HTTPS-record query to the system resolver. True if it answered."""
    if not server:
        return False
    txid = rng.getrandbits(16)
    try:
        packet = build_query(host, QTYPE_HTTPS, txid)
        family = socket.AF_INET6 if ":" in server else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(packet, (server, port))
            reply, _ = sock.recvfrom(4096)
        return len(reply) >= 12 and reply[:2] == txid.to_bytes(2, "big")
    except (OSError, ValueError, UnicodeError) as exc:
        log.debug("dns https %s failed: %s", host, exc)
        return False


class LookupCache:
    """Browser/OS cache: a host looked up recently is not asked again before its TTL.

    Re-resolving the same name every few seconds is something no browser does.
    TTLs are drawn per host (2-10 min), the range most CDNs and sites use.
    """

    def __init__(self, ttl_s: tuple[float, float] = (120, 600), max_entries: int = 512) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._until: dict[str, float] = {}

    def fresh(self, host: str, now: float) -> bool:
        return self._until.get(host, 0.0) > now

    def store(self, host: str, now: float, rng: random.Random) -> None:
        if len(self._until) >= self.max_entries:
            for h in [h for h, t in self._until.items() if t <= now] or list(self._until)[:64]:
                self._until.pop(h, None)
        self._until[host] = now + rng.uniform(*self.ttl_s)
