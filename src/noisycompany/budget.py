"""Hard limits on bytes and actions. Nothing leaves the process without a budget check."""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections import deque
from collections.abc import Callable


class Budget:
    def __init__(
        self,
        daily_bytes: int,
        max_actions_per_hour: int,
        clock: Callable[[], float] = time.time,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self.daily_bytes = daily_bytes
        self.max_actions_per_hour = max_actions_per_hour
        self._clock = clock
        self._today = today
        self._day = today()
        self._bytes_today = 0
        self._actions: deque[float] = deque()
        self._lock = threading.Lock()
        self.total_bytes = 0
        self.total_actions = 0

    def _roll(self) -> None:
        day = self._today()
        if day != self._day:
            self._day, self._bytes_today = day, 0
        cutoff = self._clock() - 3600
        while self._actions and self._actions[0] < cutoff:
            self._actions.popleft()

    @property
    def bytes_today(self) -> int:
        with self._lock:
            self._roll()
            return self._bytes_today

    def remaining_bytes(self) -> int:
        with self._lock:
            self._roll()
            return max(0, self.daily_bytes - self._bytes_today)

    def can_act(self, expected_bytes: int = 0) -> bool:
        with self._lock:
            self._roll()
            return (
                len(self._actions) < self.max_actions_per_hour
                and self._bytes_today + expected_bytes <= self.daily_bytes
            )

    def record_action(self) -> None:
        with self._lock:
            self._roll()
            self._actions.append(self._clock())
            self.total_actions += 1

    def record_bytes(self, n: int) -> None:
        with self._lock:
            self._roll()
            self._bytes_today += n
            self.total_bytes += n

    def seconds_until_action_slot(self) -> float:
        with self._lock:
            self._roll()
            if len(self._actions) < self.max_actions_per_hour:
                return 0.0
            return max(1.0, self._actions[0] + 3600 - self._clock())
