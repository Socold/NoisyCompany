"""Household masking (feature `household_masking`): hide how many people live here.

An observer who sees a household's hostnames can count its people: separate interest
clusters, separate daily rhythms, sessions that overlap. It can also tell when the home
is empty (night, holidays). Noise that simply adds three hobbies to one rhythm does not
hide that; it may even add a "fourth person" that is easy to spot.

This module draws a *virtual household* of 2 to 5 members from the local salt. Each
member owns some of the active personas and has its own chronotype (an hour shift of
the weekly rhythm). The composition is redrawn every 30 to 90 days. Sessions are picked
member by member, sometimes overlap, and keep a floor of activity during active hours,
so absences and the real head-count no longer show in the noise's shape.

Nothing is sent or stored beyond the existing salt: the household is derived from it.
The daily budget, pacing and pauses still apply.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import random
from dataclasses import dataclass

from noisycompany import rhythm


@dataclass(frozen=True)
class Member:
    index: int
    shift_h: int  # chronotype: -2 = early bird, +2 = night owl


class VirtualHousehold:
    def __init__(self, salt: str, members: tuple[int, int] = (2, 5),
                 reshuffle_days: tuple[int, int] = (30, 90)) -> None:
        self._salt = salt
        lo, hi = sorted((max(1, int(members[0])), max(1, int(members[1]))))
        self._members = (lo, hi)
        seed = self._rng("period", 0)
        r_lo, r_hi = sorted((max(1, int(reshuffle_days[0])), max(1, int(reshuffle_days[1]))))
        self.period_s = seed.randint(r_lo, r_hi) * 86400

    def _rng(self, tag: str, epoch: int) -> random.Random:
        return random.Random(hashlib.sha256(f"{self._salt}:household:{tag}:{epoch}".encode())
                             .digest())

    def epoch(self, now: dt.datetime) -> int:
        return int(now.timestamp() // self.period_s)

    def members(self, now: dt.datetime) -> list[Member]:
        rng = self._rng("members", self.epoch(now))
        n = rng.randint(*self._members)
        return [Member(i, rng.randint(-2, 2)) for i in range(n)]

    def owner(self, persona: str, now: dt.datetime) -> int:
        """Which virtual member owns this persona during the current epoch."""
        n = len(self.members(now))
        digest = hashlib.sha256(f"{self._salt}:owner:{self.epoch(now)}:{persona}".encode())
        return int.from_bytes(digest.digest()[:4], "big") % n

    @staticmethod
    def member_factor(member: Member, now: dt.datetime) -> float:
        return rhythm.factor(now - dt.timedelta(hours=member.shift_h))

    def factor(self, now: dt.datetime, floor: float = 0.35) -> float:
        """Activity of the whole virtual household, never below `floor` (presence cover)."""
        members = self.members(now)
        total = sum(self.member_factor(m, now) for m in members) / len(members)
        return max(total, floor)

    def pick_member(self, rng: random.Random, now: dt.datetime) -> Member:
        members = self.members(now)
        weights = [self.member_factor(m, now) + 0.05 for m in members]
        return rng.choices(members, weights=weights, k=1)[0]

    def affinity(self, member: Member, persona_name: str, now: dt.datetime) -> float:
        """Weight of a persona for the member in session: its own hobbies first."""
        return 1.0 if self.owner(persona_name, now) == member.index else 0.15
