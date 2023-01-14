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
