"""Measured energy of the noise on this machine (`noisycompany energy`).

docs/IMPACT.md gives network-side estimates. This measures the machine side: the CPU
time and, when the kernel exposes it, the package energy (Intel/AMD RAPL, in
/sys/class/powercap) of a number of real sessions, compared with the same duration idle.
The result per session is multiplied by the sessions per day of the configuration.

RAPL counters are root-readable on most kernels (`sudo noisycompany energy`, or a udev
rule). Without them, only CPU time is reported. A smart plug gives the wall-plug view:
see IMPACT.md.
"""

from __future__ import annotations

import resource
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

POWERCAP = Path("/sys/class/powercap")


def _packages(root: Path = POWERCAP) -> list[Path]:
    # Top-level zones only (intel-rapl:0, intel-rapl:1): sub-zones are already included.
    return sorted(p for p in root.glob("intel-rapl:*") if p.name.count(":") == 1)


def read_rapl_uj(root: Path = POWERCAP) -> int | None:
    """Sum of package energy counters in microjoules, or None if unreadable."""
    total = 0
    zones = _packages(root)
    if not zones:
        return None
    try:
        for z in zones:
            total += int((z / "energy_uj").read_text())
    except (OSError, ValueError):
        return None
    return total


def _delta_uj(before: int, after: int, root: Path = POWERCAP) -> int:
    if after >= before:
        return after - before
    try:  # counter wrapped
        wrap = sum(int((z / "max_energy_range_uj").read_text()) for z in _packages(root))
    except (OSError, ValueError):
        return 0
    return after + wrap - before


@dataclass
class Measurement:
    sessions: int
    seconds: float
    cpu_s: float
    joules_run: float | None
    joules_idle: float | None

    @property
    def joules_per_session(self) -> float | None:
        if self.joules_run is None or self.joules_idle is None or not self.sessions:
            return None
        return max(0.0, self.joules_run - self.joules_idle) / self.sessions

    def wh_per_day(self, sessions_per_day: float) -> float | None:
        j = self.joules_per_session
        return None if j is None else j * sessions_per_day / 3600


def _cpu() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def measure(run_session: Callable[[], None], sessions: int,
            read: Callable[[], int | None] = read_rapl_uj,
            sleep: Callable[[float], None] = time.sleep,
            clock: Callable[[], float] = time.monotonic) -> Measurement:
    """Run `sessions` sessions back to back, then stay idle as long, and compare."""
    cpu0, e0, t0 = _cpu(), read(), clock()
    for _ in range(sessions):
        run_session()
    cpu1, e1, t1 = _cpu(), read(), clock()
    duration = t1 - t0
    sleep(duration)  # same wall time idle: the machine's baseline over that period
    e2 = read()
    run = idle = None
    if None not in (e0, e1, e2):
        run = _delta_uj(e0, e1) / 1e6  # type: ignore[arg-type]
        idle = _delta_uj(e1, e2) / 1e6  # type: ignore[arg-type]
    return Measurement(sessions, duration, cpu1 - cpu0, run, idle)
