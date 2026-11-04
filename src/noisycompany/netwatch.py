"""Back off while the user's own traffic is high (Linux /proc/net/dev).

noisycompany must never compete with a video call or a download. We sample interface
counters, subtract what noisycompany itself transferred, and pause above a threshold.
On non-Linux systems the watcher reports "idle" and only the budget applies.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

PROC_NET_DEV = Path("/proc/net/dev")
IGNORED_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "tun", "tap", "wg", "tailscale")


def read_counters(text: str, interface: str = "auto") -> int:
    """Return rx+tx bytes for the interface (or all physical-looking ones)."""
    total = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        name = name.strip()
        if interface == "auto":
            if name.startswith(IGNORED_PREFIXES):
                continue
        elif name != interface:
            continue
        fields = data.split()
        if len(fields) >= 9:
            total += int(fields[0]) + int(fields[8])
    return total


class NetWatch:
    def __init__(
        self,
        pause_above_kbps: float,
        interface: str = "auto",
        enabled: bool = True,
        reader: Callable[[], str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.threshold_bps = pause_above_kbps * 1000 / 8
        self.interface = interface
        self._reader = reader or (lambda: PROC_NET_DEV.read_text())
        self._clock = clock
        self.enabled = enabled and (reader is not None or PROC_NET_DEV.exists())
        self._last: tuple[float, int] | None = None
        self._own_since_last = 0
        self.last_rate_bps = 0.0

    def note_own_bytes(self, n: int) -> None:
        self._own_since_last += n

    def user_rate_bps(self) -> float:
        """Bytes/s of non-noisycompany traffic since the previous call (0 on first call)."""
        if not self.enabled:
            return 0.0
        try:
            counters = read_counters(self._reader(), self.interface)
        except (OSError, ValueError):
            return 0.0
        now = self._clock()
        rate = 0.0
        if self._last is not None:
            t0, c0 = self._last
            elapsed = max(now - t0, 1e-3)
            rate = max(0.0, (counters - c0 - self._own_since_last) / elapsed)
        self._last = (now, counters)
        self._own_since_last = 0
        self.last_rate_bps = rate
        return rate

    def user_online(self, active_kbps: float) -> bool:
        """Fresh sample: is the user's own traffic above active_kbps?"""
        return self.enabled and self.user_rate_bps() > active_kbps * 1000 / 8

    def busy(self) -> bool:
        return self.enabled and self.user_rate_bps() > self.threshold_bps
