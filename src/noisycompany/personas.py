"""Coherent decoy personas, rotated slowly.

A tracker or ISP that sees uniformly random noise can drop it with a simple filter
(no repeat visits, no topical coherence). A small set of stable, plausible interests,
changing every few days, looks like a person and survives that filtering better.
The active set is derived from a local random salt and the rotation period, so it is
stable across restarts but not predictable by anyone who does not have the salt.
"""

from __future__ import annotations

import hashlib
import random
import secrets
import time
from pathlib import Path


def _salt(state_dir: Path | None) -> str:
    if state_dir is None:
        return secrets.token_hex(16)
    path = state_dir / "salt"
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        state_dir.mkdir(parents=True, exist_ok=True)
        value = secrets.token_hex(16)
        path.write_text(value)
        path.chmod(0o600)
        return value


class PersonaRotator:
    def __init__(
        self,
        personas: dict[str, dict[str, list[str]]],
        active_count: int,
        rotate_days: float,
        state_dir: Path | None = None,
        clock=time.time,
    ) -> None:
        self.personas = personas
        self.active_count = min(active_count, len(personas))
        self.period_s = max(rotate_days, 0.01) * 86400
        self._salt = _salt(state_dir)
        self._clock = clock

    def epoch(self) -> int:
        return int(self._clock() // self.period_s)

    def _rng(self, tag: str, epoch: int) -> random.Random:
        return random.Random(hashlib.sha256(f"{self._salt}:{tag}:{epoch}".encode()).digest())

    def active(self, drift_main_days: float | None = None) -> list[str]:
        """Active personas, first one = main hobby.

        With drift_main_days (feature persona_drift), the main hobby follows its own,
        much longer period and only the secondary interests rotate.
        """
        names = sorted(self.personas)
        if not drift_main_days or self.active_count < 2:
            return self._rng("set", self.epoch()).sample(names, self.active_count)
        main_epoch = int(self._clock() // (max(drift_main_days, 0.01) * 86400))
        main = self._rng("main", main_epoch).choice(names)
        rest = [n for n in names if n != main]
        return [main, *self._rng("set", self.epoch()).sample(rest, self.active_count - 1)]

    def pick(self, rng: random.Random,
             drift_main_days: float | None = None) -> tuple[str, dict[str, list[str]]]:
        # Weighted: the first active persona is the "main hobby", visited more often.
        names = self.active(drift_main_days)
        weights = [len(names) - i for i in range(len(names))]
        name = rng.choices(names, weights=weights, k=1)[0]
        return name, self.personas[name]
