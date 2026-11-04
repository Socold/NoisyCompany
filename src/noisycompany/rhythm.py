"""Weekly and seasonal rhythm (feature `weekly_rhythm`).

Hour of day and weekday are among the most telling features of the separability study:
a generator that is equally busy on a Tuesday 9 am and a Sunday 9 am stands out. This
module returns an activity factor that scales the mean gap between sessions. It never
raises the daily budget: the caps and pacing still apply.
"""

from __future__ import annotations

import datetime as dt

# Activity by hour (0-23), 1.0 = configured mean rate.
WEEKDAY = (0, 0, 0, 0, 0, 0, .2, .5, .7, .6, .5, .6, 1.1, 1.0, .6, .5, .6, .8,
           1.1, 1.4, 1.6, 1.5, 1.1, .5)
# Weekends and holidays: later mornings, a spread-out afternoon.
WEEKEND = (0, 0, 0, 0, 0, 0, 0, .1, .3, .6, .9, 1.1, 1.0, .9, 1.0, 1.1, 1.1, 1.1,
           1.2, 1.3, 1.4, 1.3, 1.0, .5)
# Fixed-date days off common to most of Europe (movable feasts are left out).
HOLIDAYS = {(1, 1), (5, 1), (8, 15), (11, 1), (12, 24), (12, 25), (12, 26), (12, 31)}
# Less screen time in high summer.
SEASON = {7: .85, 8: .8, 12: 1.1, 1: 1.05}


def day_off(day: dt.date) -> bool:
    return day.weekday() >= 5 or (day.month, day.day) in HOLIDAYS


def factor(now: dt.datetime) -> float:
    """Activity multiplier for this moment, 0 = sleep (budget pacing still applies)."""
    table = WEEKEND if day_off(now.date()) else WEEKDAY
    # Linear blend between hours so the rate does not jump at :00.
    h = now.hour
    frac = now.minute / 60
    base = table[h] * (1 - frac) + table[(h + 1) % 24] * frac
    return round(base * SEASON.get(now.month, 1.0), 3)


def session_gap(mean_gap_s: float, now: dt.datetime, floor: float = 0.05) -> float:
    """Mean gap to the next session: shorter when the household is usually online."""
    return mean_gap_s / max(factor(now), floor)
