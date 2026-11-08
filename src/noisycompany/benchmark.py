"""Public separability benchmark: how well does each release hide its noise?

Reproducible and offline. The real engine runs for simulated days on a simulated clock,
with a fake network that serves synthetic persona pages (links, third-party embeds), and
writes its labelled log as usual. A synthetic household DNS trace stands for the real
traffic. The separability study then scores each configuration by ROC AUC.

The synthetic household is a model, not a measurement: page loads in evening and
weekend peaks, a Zipf choice of favourite sites, 5-25 third-party hosts per page, and
periodic device chatter. It is good at tracking *progress between releases*; it does not
replace `noisycompany study` on your own trace.
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
import random
import threading
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from noisycompany import config, rhythm, study
from noisycompany.budget import Budget
from noisycompany.engine import Engine
from noisycompany.netwatch import NetWatch
from noisycompany.web import REQUEST_OVERHEAD, Fetcher, FetchResult

START = dt.datetime(2026, 3, 2)  # a Monday, outside holidays
CDN = [f"{p}.{d}" for p in ("cdn", "static", "img", "fonts", "api") for d in (
    "cloudfront.net", "akamaized.net", "fastly.net", "jsdelivr.net", "gstatic.com",
    "wp.com", "cloudflare.com", "bootstrapcdn.com")]
SITES = [f"{w}.{tld}" for w in ("news", "mail", "video", "shop", "bank", "weather",
                                "maps", "social", "forum", "recipes", "sport", "music",
                                "travel", "wiki", "games", "school", "jobs", "photos")
         for tld in ("com", "fr", "net")]
CHATTER = ["time.example-os.com", "push.example-phone.com", "telemetry.example-tv.net",
           "connectivity-check.example.org"]

CONFIGS = {
    "baseline (eco)": {},
    "+ weekly_rhythm": {"weekly_rhythm": True},
    "+ dns_coherence": {"dns_coherence": True},
    "+ third_party_bursts": {"third_party_bursts": True},
    "all 2.2 realism switches": {"weekly_rhythm": True, "dns_coherence": True,
                                 "third_party_bursts": True},
    "+ page_load_bursts": {"weekly_rhythm": True, "dns_coherence": True,
                           "page_load_bursts": True},
    "+ interleave_with_user": {"weekly_rhythm": True, "dns_coherence": True,
                               "page_load_bursts": True, "interleave_with_user": True},
    "+ browser_dns": {"weekly_rhythm": True, "dns_coherence": True,
                      "page_load_bursts": True, "browser_dns": True},
    "+ household_masking": {"weekly_rhythm": True, "dns_coherence": True,
                            "page_load_bursts": True, "browser_dns": True,
                            "household_masking": True},
}


class _SimClock:
    def __init__(self, start: dt.datetime) -> None:
        self.t = start.timestamp()

    def now(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.t)


class _FakeFetcher(Fetcher):
    """Serves synthetic pages: same-domain links and a few third-party embeds."""

    def __init__(self, base: Fetcher, rng: random.Random) -> None:
        super().__init__(base.user_agent, base.timeout_s, base.max_response_bytes,
                         False, 0.0)
        self.rng = rng

    def url_allowed(self, url: str) -> bool:
        return True

    def host_ready_in(self, url: str, now: float | None = None) -> float:
        return 0.0

    def allowed_by_robots(self, url: str) -> tuple[bool, int]:
        return True, 0

    def fetch(self, url: str) -> FetchResult | None:
        host = urllib.parse.urlsplit(url).hostname or ""
        links = "".join(f'<a href="https://{host}/p/{self.rng.randrange(500)}">x</a>'
                        for _ in range(8))
        embeds = "".join(f'<script src="https://{h}/a.js"></script>'
                         for h in self.rng.sample(CDN, self.rng.randint(5, 25)))
        size = int(self.max_response_bytes * self.rng.uniform(0.3, 0.9))
        return FetchResult(url, 200, REQUEST_OVERHEAD + size, f"<html>{embeds}{links}</html>")

    def fetch_asset(self, url: str) -> int:
        return REQUEST_OVERHEAD + self.asset_cap // 2


class _HouseholdNetWatch(NetWatch):
    """User traffic as seen by the counter: 'online' within 2 min of a household event."""

    def __init__(self, household: list[study.Event], clock: _SimClock) -> None:
        super().__init__(400, reader=lambda: "", clock=lambda: clock.t)
        self.times = [e.ts for e in household]
        self.sim = clock

    def user_rate_bps(self) -> float:
        i = bisect.bisect_right(self.times, self.sim.t)
        online = i > 0 and self.sim.t - self.times[i - 1] < 120
        self.last_rate_bps = 25_000.0 if online else 0.0  # 200 kbps, under the pause level
        return self.last_rate_bps


def simulate_noise(switches: dict[str, bool], days: int, seed: int,
                   cfg: dict | None = None, options: dict | None = None,
                   keep_log: Path | None = None,
                   household: list[study.Event] | None = None) -> list[study.Event]:
    """Run the real engine offline; optionally copy its labelled log to keep_log."""
    rng = random.Random(seed)
    clock = _SimClock(START)
    end = clock.t + days * 86400
    with TemporaryDirectory() as tmp:
        state = Path(tmp)
        cfg = cfg or config.load(preset="eco")
        cfg["netwatch"]["enabled"] = False
        stop = threading.Event()
        eng = Engine(cfg, config.load_personas(cfg), state, rng=rng, stop=stop, now=clock.now)
        eng.budget = Budget(eng.budget.daily_bytes, eng.budget.max_actions_per_hour,
                            clock=lambda: clock.t, today=lambda: clock.now().date())
        eng.base_cap = eng.budget.daily_bytes
        eng.fetcher = _FakeFetcher(eng.fetcher, rng)
        if household is not None:
            eng.netwatch = _HouseholdNetWatch(household, clock)
        eng.lookup = lambda host: (True, 300, "dns")  # type: ignore[method-assign]
        eng.save_stats = lambda: None  # type: ignore[method-assign]
        eng.options.update(options or {})
        eng.features.set("labelled_log", True)
        for fid, on in switches.items():
            eng.features.set(fid, on)

        def sleep(seconds: float) -> bool:
            clock.t += max(0.0, seconds)
            if clock.t >= end:
                stop.set()
                return False
            return True

        eng._sleep = sleep  # type: ignore[method-assign]
        eng.run()
        log = state / "labelled.jsonl"
        if keep_log:
            keep_log.write_text(log.read_text("utf-8") if log.exists() else "", "utf-8")
        return study.load_noise(log) if log.exists() else []


def _zipf(rng: random.Random, items: list[str], s: float = 1.2) -> str:
    weights = [1 / (i + 1) ** s for i in range(len(items))]
    return rng.choices(items, weights=weights, k=1)[0]


def simulate_household(days: int, seed: int) -> list[study.Event]:
    rng = random.Random(seed)
    sites = SITES[:]
    rng.shuffle(sites)
    out: list[study.Event] = []
    t0 = START.timestamp()
    for minute in range(days * 1440):
        ts = t0 + minute * 60
        now = dt.datetime.fromtimestamp(ts)
        if minute % 60 == 0:  # devices phone home, day and night
            out += [study.Event(ts + rng.uniform(0, 50), h) for h in CHATTER if rng.random() < .7]
        if rng.random() < rhythm.factor(now) * 0.08:  # a browsing session starts
            t = ts + rng.uniform(0, 60)
            for _ in range(rng.randint(1, 8)):
                site = _zipf(rng, sites)
                out.append(study.Event(t, site))
                for h in rng.sample(CDN, rng.randint(5, 25)):
                    out.append(study.Event(t + rng.uniform(0.05, 1.5), h))
                t += rng.expovariate(1 / 45)
    return sorted(out, key=lambda e: e.ts)


@dataclass
class Row:
    name: str
    auc: float
    noise_events: int
    top_features: list[str]


def run(days: int = 14, seed: int = 7) -> Iterator[Row]:
    human = simulate_household(days, seed)
    for name, switches in CONFIGS.items():
        noise = simulate_noise(switches, days, seed, household=human)
        res = study.run(noise, human, window_s=600, seed=seed)
        top = sorted(res.weights, key=lambda k: -abs(res.weights[k]))[:3]
        yield Row(name, res.auc, len(noise), top)


def as_markdown(rows: list[Row], days: int, seed: int, version: str) -> str:
    lines = [f"| Configuration (v{version}, {days} simulated days, seed {seed}) | ROC AUC | "
             "Noise events | Most telling features |", "|---|---|---|---|"]
    lines += [f"| {r.name} | {r.auc:.2f} | {r.noise_events} | {', '.join(r.top_features)} |"
              for r in rows]
    return "\n".join(lines) + "\n"


def as_json(rows: list[Row]) -> str:
    return json.dumps([r.__dict__ for r in rows], indent=2)
