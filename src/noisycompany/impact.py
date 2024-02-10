"""Bandwidth and environmental impact estimates for a given configuration.

Figures are deliberately given as ranges: the energy intensity of networks per GB is
one of the most disputed numbers in the field (from ~0.06 kWh/GB for 2015-era averaged
models down to ~0.005 kWh/GB for recent fixed networks, and close to zero in marginal
terms since network power barely varies with load). See docs/IMPACT.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noisycompany.config import TimeRange
from noisycompany.dns import DNS_BYTES_ESTIMATE
from noisycompany.doh import DOH_BYTES_ESTIMATE
from noisycompany.web import REQUEST_OVERHEAD

KWH_PER_GB_LOW = 0.005   # recent fixed-network estimates (attributional, 2024-2025)
KWH_PER_GB_HIGH = 0.06   # older averaged estimate (Aslan et al. 2018, 2015 data)
HD_VIDEO_MB_PER_MIN = 50  # ~3 GB/hour for 1080p streaming
# Typical average page fill ratio of the size cap (HTML pages are rarely at the cap).
PAGE_FILL = 0.6


@dataclass
class Estimate:
    active_hours_per_day: float
    sessions_per_day: float
    dns_lookups_per_day: float
    pages_per_day: float
    mb_per_day_expected: float
    mb_per_day_cap: float
    mb_per_month: float
    avg_kbps_when_active: float
    kwh_per_month: tuple[float, float]
    gco2_per_month: tuple[float, float]
    hd_video_seconds_per_day: float

    def as_text(self) -> str:
        lo_k, hi_k = self.kwh_per_month
        lo_c, hi_c = self.gco2_per_month
        return "\n".join([
            f"Active hours/day         : {self.active_hours_per_day:.1f} h",
            f"Sessions/day             : ~{self.sessions_per_day:.0f}",
            f"DNS lookups/day          : ~{self.dns_lookups_per_day:.0f}",
            f"Pages fetched/day        : ~{self.pages_per_day:.0f}",
            f"Data/day (expected)      : ~{self.mb_per_day_expected:.1f} MB "
            f"(hard cap {self.mb_per_day_cap:.0f} MB)",
            f"Data/month (expected)    : ~{self.mb_per_month:.0f} MB",
            f"Average rate when active : ~{self.avg_kbps_when_active:.2f} kbit/s",
            f"Equivalent HD video/day  : ~{self.hd_video_seconds_per_day:.0f} s",
            f"Network energy/month     : {lo_k * 1000:.1f} to {hi_k * 1000:.1f} Wh",
            f"CO2e/month               : {lo_c:.2f} to {hi_c:.2f} g "
            f"(grid intensity given)",
        ])


def active_hours(cfg: dict[str, Any]) -> float:
    minutes = 0
    for r in cfg["schedule"]["active_hours"]:
        tr = TimeRange.parse(r)
        span = tr.end_min - tr.start_min
        minutes += span if span >= 0 else span + 1440
    return min(minutes, 1440) / 60


def estimate(cfg: dict[str, Any], grid_gco2_per_kwh: float = 50.0) -> Estimate:
    """Expected traffic for cfg. grid default 50 g/kWh ~ France; EU avg ~250."""
    sched, dns, http, budget = cfg["schedule"], cfg["dns"], cfg["http"], cfg["budget"]
    hours = active_hours(cfg)
    mean_dwell = sum(sched["dwell_s"]) / 2
    mean_pages = sum(sched["pages_per_session"]) / 2
    mean_lookups = sum(dns["lookups_per_session"]) / 2
    w_dns = dns["weight"] if dns["enabled"] else 0.0
    w_http = http["weight"] if http["enabled"] else 0.0
    total_w = w_dns + w_http
    p_dns, p_http = w_dns / total_w, w_http / total_w
    mean_session_duration = p_http * mean_pages * mean_dwell + p_dns * 2
    cycle = sched["mean_session_gap_s"] + mean_session_duration
    sessions = hours * 3600 / cycle
    hourly_cap_sessions = budget["max_actions_per_hour"] * hours / max(
        p_dns * mean_lookups + p_http * mean_pages, 1e-9)
    sessions = min(sessions, hourly_cap_sessions)
    lookups = sessions * p_dns * mean_lookups
    pages = sessions * p_http * mean_pages
    page_bytes = REQUEST_OVERHEAD + budget["max_response_kb"] * 1024 * PAGE_FILL
    dns_cost = (DOH_BYTES_ESTIMATE if cfg.get("features", {}).get("doh_sink")
                else DNS_BYTES_ESTIMATE)
    expected = lookups * dns_cost + pages * page_bytes
    # robots.txt is fetched once per origin; small, counted as 5% overhead.
    expected *= 1.05
    cap = budget["daily_mb"] * 1_000_000
    per_day = min(expected, cap)
    mb_day = per_day / 1_000_000
    gb_month = mb_day * 30 / 1000
    kwh = (gb_month * KWH_PER_GB_LOW, gb_month * KWH_PER_GB_HIGH)
    return Estimate(
        active_hours_per_day=hours,
        sessions_per_day=sessions,
        dns_lookups_per_day=lookups,
        pages_per_day=pages,
        mb_per_day_expected=mb_day,
        mb_per_day_cap=budget["daily_mb"],
        mb_per_month=mb_day * 30,
        avg_kbps_when_active=(per_day * 8 / 1000) / max(hours * 3600, 1),
        kwh_per_month=kwh,
        gco2_per_month=(kwh[0] * grid_gco2_per_kwh, kwh[1] * grid_gco2_per_kwh),
        hd_video_seconds_per_day=mb_day / HD_VIDEO_MB_PER_MIN * 60,
    )
