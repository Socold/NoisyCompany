"""Real third-party host sets per persona site (feature `real_third_parties`).

A real page load resolves the page host and then 5-40 other hosts (CDNs, fonts, video
players, APIs), most of them loaded by JavaScript and absent from the raw HTML the
daemon reads. data/third_parties.json records, for each persona seed page, the hosts a
headless Chromium contacted and when (ms after navigation start), trackers removed. It
is produced by tools/third_party_snapshot.py and refreshed by a monthly workflow.

Replaying that list, with the real order and spacing, makes a noise "visit" look like a
browser's page load to a DNS observer, without downloading anything.
"""

from __future__ import annotations

import json
import logging
import random
from functools import lru_cache
from importlib import resources

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _sites() -> dict[str, list[tuple[str, int]]]:
    try:
        raw = json.loads(resources.files("noisycompany").joinpath("data/third_parties.json")
                         .read_text("utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("third_parties.json unreadable: %s", exc)
        return {}
    out: dict[str, list[tuple[str, int]]] = {}
    for site, hosts in raw.get("sites", {}).items():
        out[site.lower()] = [(str(h).lower(), int(ms)) for h, ms in hosts]
    return out


def snapshot_date() -> str:
    try:
        raw = json.loads(resources.files("noisycompany").joinpath("data/third_parties.json")
                         .read_text("utf-8"))
        return str(raw.get("generated", ""))
    except (OSError, ValueError):
        return ""


def known(page_host: str) -> list[tuple[str, int]]:
    """Recorded hosts for this page host (www. and bare forms are interchangeable)."""
    host = page_host.lower().rstrip(".")
    sites = _sites()
    if host in sites:
        return sites[host]
    alt = host[4:] if host.startswith("www.") else "www." + host
    return sites.get(alt, [])


def page_load(page_host: str, rng: random.Random, keep: float = 0.85,
              max_gap_s: float = 2.5) -> list[tuple[str, float]]:
    """(host, seconds to wait before it) for one simulated load of this page.

    Each recorded host is kept with probability `keep` (caches, A/B tests and lazy
    loading make real loads vary), the recorded order is kept, and the recorded gaps are
    jittered by 0.6x-1.4x and capped so a slow JS host does not stall a session.
    """
    out: list[tuple[str, float]] = []
    previous = 0
    for host, ms in known(page_host):
        if rng.random() > keep:
            continue
        gap = max(0, ms - previous) / 1000 * rng.uniform(0.6, 1.4)
        out.append((host, min(gap, max_gap_s)))
        previous = ms
    return out
