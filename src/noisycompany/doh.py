"""DNS-over-HTTPS noise (RFC 8484, GET with base64url wire-format query).

When the browser uses DoH, plain DNS noise goes to a different resolver than the real
queries and is trivially separated. This sink sends the noise where the real queries go.
"""

from __future__ import annotations

import base64
import logging
import random
import struct
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# TLS handshake + HTTP headers + small DNS payloads, rough on-the-wire estimate.
DOH_BYTES_ESTIMATE = 5_000
QTYPES = {"A": 1, "AAAA": 28, "HTTPS": 65}


def build_query(name: str, qtype: str = "A", query_id: int = 0) -> bytes:
    """DNS wire-format query. ID 0 as recommended by RFC 8484 for cache friendliness."""
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)  # RD=1, one question
    labels = b""
    for label in name.rstrip(".").split("."):
        raw = label.encode("idna")
        if not 0 < len(raw) < 64:
            raise ValueError(f"invalid label in {name!r}")
        labels += bytes([len(raw)]) + raw
    return header + labels + b"\x00" + struct.pack("!HH", QTYPES[qtype], 1)


def resolve(url: str, name: str, user_agent: str, timeout: float = 6.0,
            rng: random.Random | None = None) -> bool:
    qtype = (rng or random).choice(["A", "AAAA", "HTTPS"])
    try:
        query = build_query(name, qtype)
    except (ValueError, UnicodeError):
        return False
    param = base64.urlsafe_b64encode(query).rstrip(b"=").decode()
    req = urllib.request.Request(  # noqa: S310 - https URL from config
        f"{url}?dns={param}",
        headers={"Accept": "application/dns-message", "User-Agent": user_agent},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200 and len(resp.read(4096)) >= 12
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("doh %s failed: %s", name, exc)
        return False
