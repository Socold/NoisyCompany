"""Detect metered connections through NetworkManager (`nmcli`). Linux only."""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404 - fixed argv, no shell
import time
from collections.abc import Callable


def parse_nmcli(output: str) -> bool:
    """`nmcli -t -f GENERAL.METERED device show` lines -> any 'yes'?"""
    for line in output.splitlines():
        _, _, value = line.partition(":")
        if value.strip().lower().startswith("yes"):
            return True
    return False


def _run_nmcli() -> str:
    exe = shutil.which("nmcli")
    if not exe:
        return ""
    try:
        return subprocess.run(  # noqa: S603
            [exe, "-t", "-f", "GENERAL.METERED", "device", "show"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class MeteredProbe:
    def __init__(self, runner: Callable[[], str] = _run_nmcli, ttl_s: float = 300,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._runner, self._ttl, self._clock = runner, ttl_s, clock
        self._cached: tuple[float, bool] | None = None

    def metered(self) -> bool:
        now = self._clock()
        if self._cached and now - self._cached[0] < self._ttl:
            return self._cached[1]
        value = parse_nmcli(self._runner())
        self._cached = (now, value)
        return value
