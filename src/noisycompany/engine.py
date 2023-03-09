"""The scheduler: human-like sessions under hard budget and politeness limits."""

from __future__ import annotations

import datetime as dt
import json
import logging
import random
import threading
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from noisycompany import dns, doh
from noisycompany.budget import Budget
from noisycompany.config import PRESETS, TimeRange, load_locale_personas
from noisycompany.features import FeatureSet
from noisycompany.metered import MeteredProbe
from noisycompany.netwatch import NetWatch
from noisycompany.personas import PersonaRotator
from noisycompany.server import LocalServer
from noisycompany.web import REQUEST_OVERHEAD, Fetcher, extract_links, host_allowed, is_blocked

log = logging.getLogger(__name__)


@dataclass
class Stats:
    sessions: int = 0
    dns_ok: int = 0
    dns_fail: int = 0
    pages_ok: int = 0
    pages_fail: int = 0
    robots_denied: int = 0
    paused_busy: int = 0
    paused_budget: int = 0
    bytes: int = 0


class Engine:
    def __init__(
        self,
        cfg: dict[str, Any],
        personas: dict[str, dict[str, list[str]]],
        state_dir: Path | None = None,
        dry_run: bool = False,
        rng: random.Random | None = None,
        stop: threading.Event | None = None,
        now=dt.datetime.now,
        metered_probe: MeteredProbe | None = None,
    ) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self.rng = rng or random.SystemRandom()
        self.stop = stop or threading.Event()
        self.state_dir = state_dir
        self._now = now
        self.stats = Stats()
        b = cfg["budget"]
        self.budget = Budget(int(b["daily_mb"] * 1_000_000), b["max_actions_per_hour"])
        nw = cfg["netwatch"]
        self.netwatch = NetWatch(nw["pause_above_kbps"], nw["interface"],
                                 enabled=nw["enabled"] and not dry_run)
        self.rotator = PersonaRotator(personas, cfg["personas"]["active_count"],
                                      cfg["personas"]["rotate_days"], state_dir)
        h = cfg["http"]
        self.fetcher = Fetcher(h["user_agent"], h["timeout_s"], b["max_response_kb"] * 1024,
                               h["respect_robots_txt"], h["per_host_delay_s"])
        self.page_estimate = REQUEST_OVERHEAD + b["max_response_kb"] * 1024
        self.ranges = [TimeRange.parse(r) for r in cfg["schedule"]["active_hours"]]
        self.features = FeatureSet(cfg, state_dir)
        self.options: dict[str, Any] = cfg.get("features", {}).get("options", {})
        locale = load_locale_personas(cfg) if self.options.get("locale_packs") else {}
        self.locale_rotator = (
            PersonaRotator(locale, cfg["personas"]["active_count"],
                           cfg["personas"]["rotate_days"], state_dir) if locale else None)
        self.metered_probe = metered_probe or MeteredProbe()
        self.metered = False
        self.base_cap = self.budget.daily_bytes
        self.eco_cap = min(self.base_cap, int(PRESETS["eco"]["budget"]["daily_mb"] * 1_000_000))
        self.state = "starting"
        self.servers = {
            "metrics": LocalServer(int(self.options.get("metrics_port", 9789)), self, "metrics"),
            "dashboard": LocalServer(int(self.options.get("dashboard_port", 9788)), self,
                                     "dashboard"),
        }
        log_path = self.options.get("labelled_log_path") or (
            str(state_dir / "labelled.jsonl") if state_dir else "")
        self.labelled_path = Path(log_path) if log_path else None

    # ---------------------------------------------------------------- features
    def drift_days(self) -> float | None:
        if self.features.enabled("persona_drift"):
            return float(self.options.get("drift_main_days", 120))
        return None

    def refresh_features(self) -> None:
        """Apply switch changes (dashboard / CLI) between sessions."""
        self.features.reload()
        self.metered = (self.features.enabled("metered_guard") and not self.dry_run
                        and self.metered_probe.metered())
        self.budget.daily_bytes = self.eco_cap if self.metered else self.base_cap
        for name, srv in self.servers.items():
            srv.sync(self.features.enabled(name))

    def status(self) -> dict[str, Any]:
        return {
            "stats": asdict(self.stats),
            "bytes_today": self.budget.bytes_today,
            "daily_cap_bytes": self.budget.daily_bytes,
            "metered": self.metered,
            "state": self.state,
            "active_personas": self.active_personas(),
            "preset": self.cfg["general"]["preset"],
        }

    def active_personas(self) -> list[str]:
        out = self.rotator.active(self.drift_days())
        if self.locale_rotator and self.features.enabled("locale_packs"):
            out += self.locale_rotator.active(self.drift_days())
        return out

    def label(self, kind: str, target: str, ok: bool, nbytes: int, persona: str) -> None:
        """Ground-truth record for detection testing (feature labelled_log)."""
        if not self.labelled_path or not self.features.enabled("labelled_log"):
            return
        rec = {"ts": self._now().astimezone().isoformat(timespec="seconds"),
               "label": "benign-noise", "generator": "noisycompany", "kind": kind,
               "target": target, "ok": ok, "bytes": nbytes, "persona": persona,
               "dry_run": self.dry_run}
        try:
            self.labelled_path.parent.mkdir(parents=True, exist_ok=True)
            with self.labelled_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError as exc:
            log.warning("labelled log: %s", exc)

    # ---------------------------------------------------------------- helpers
    def _sleep(self, seconds: float) -> bool:
        """Interruptible sleep. Returns False if asked to stop."""
        return not self.stop.wait(max(0.0, seconds))

    def _uniform(self, pair: list[float]) -> float:
        return self.rng.uniform(pair[0], pair[1])

    def _randint(self, pair: list[int]) -> int:
        return self.rng.randint(int(pair[0]), int(pair[1]))

    def is_active_time(self) -> bool:
        now = self._now()
        minute = now.hour * 60 + now.minute
        return any(r.contains(minute) for r in self.ranges)

    def active_fraction_elapsed(self) -> float:
        """Share of today's active minutes already past (0..1)."""
        now = self._now()
        minute = now.hour * 60 + now.minute
        total = sum(1 for m in range(1440) if any(r.contains(m) for r in self.ranges))
        past = sum(1 for m in range(minute + 1) if any(r.contains(m) for r in self.ranges))
        return past / total if total else 1.0

    def ahead_of_pace(self) -> bool:
        """Spread the daily budget over the active window instead of burning it at 8 am."""
        allowed = self.budget.daily_bytes * min(1.0, self.active_fraction_elapsed() + 0.1)
        return self.budget.bytes_today > allowed

    def _spend(self, n: int) -> None:
        self.budget.record_bytes(n)
        self.netwatch.note_own_bytes(n)
        self.stats.bytes += n

    def save_stats(self) -> None:
        if not self.state_dir:
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(self.stats) | {
            "bytes_today": self.budget.bytes_today,
            "active_personas": self.active_personas(),
            "updated": self._now().isoformat(timespec="seconds"),
        }
        tmp = self.state_dir / "stats.json.tmp"
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.state_dir / "stats.json")

    # ---------------------------------------------------------------- gates
    def wait_for_slot(self) -> bool:
        """Block until we are allowed to act. Returns False if stopping."""
        while not self.stop.is_set():
            self.refresh_features()
            if not self.is_active_time():
                self.state = "outside active hours"
                if not self._sleep(60):
                    return False
                continue
            if self.netwatch.busy():
                self.stats.paused_busy += 1
                self.state = "paused: your own traffic is high"
                log.debug("user traffic high, backing off")
                if not self._sleep(30 + self.rng.uniform(0, 30)):
                    return False
                continue
            wait = self.budget.seconds_until_action_slot()
            if (wait or self.budget.remaining_bytes() < self.page_estimate
                    or self.ahead_of_pace()):
                self.stats.paused_budget += 1
                self.state = "waiting: budget pacing"
                log.info("budget reached, sleeping")
                if not self._sleep(wait or 600):
                    return False
                continue
            self.state = "running"
            return True
        return False

    # ---------------------------------------------------------------- sessions
    def dns_session(self, domains: list[str], persona: str = "") -> None:
        use_doh = self.features.enabled("doh_sink")
        cost = doh.DOH_BYTES_ESTIMATE if use_doh else dns.DNS_BYTES_ESTIMATE
        for _ in range(self._randint(self.cfg["dns"]["lookups_per_session"])):
            if not self.budget.can_act(cost):
                return
            host = dns.candidate_hosts(domains, self.rng)
            self.budget.record_action()
            if self.dry_run:
                ok = True
            elif use_doh:
                ok = doh.resolve(self.options.get("doh_url", ""), host,
                                 self.cfg["http"]["user_agent"], rng=self.rng)
            else:
                ok = dns.resolve(host)
            self._spend(cost)
            self.label("doh" if use_doh else "dns", host, ok, cost, persona)
            if ok:
                self.stats.dns_ok += 1
            else:
                self.stats.dns_fail += 1
            log.debug("dns %s %s", host, "ok" if ok else "fail")
            if not self._sleep(self.rng.uniform(0.3, 3.0)):
                return

    def _entry_url(self, persona: dict[str, list[str]]) -> str:
        if self.rng.random() < 0.25 and "en.wikipedia.org" in persona["domains"]:
            title = self.rng.choice(persona["queries"]).strip().capitalize().replace(" ", "_")
            return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title)
        return self.rng.choice(persona["seeds"])

    def http_session(self, persona: dict[str, list[str]], name: str = "") -> None:
        sched, http, safety = self.cfg["schedule"], self.cfg["http"], self.cfg["safety"]
        url: str | None = self._entry_url(persona)
        for _ in range(self._randint(sched["pages_per_session"])):
            if url is None or self.stop.is_set():
                return
            if not self.budget.can_act(self.page_estimate):
                return
            wait = self.fetcher.host_ready_in(url)
            if wait > 0 and not self._sleep(wait):
                return
            self.budget.record_action()
            if self.dry_run:
                log.info("[dry-run] GET %s", url)
                self._spend(self.page_estimate)
                self.label("http", url, True, self.page_estimate, name)
                self.stats.pages_ok += 1
                links: list[str] = []
            else:
                allowed, spent = self.fetcher.allowed_by_robots(url)
                self._spend(spent)
                if not allowed:
                    self.stats.robots_denied += 1
                    self.label("robots_denied", url, False, spent, name)
                    return
                res = self.fetcher.fetch(url)
                if res is None or res.status >= 400:
                    self.stats.pages_fail += 1
                    self._spend(res.wire_bytes if res else REQUEST_OVERHEAD)
                    self.label("http", url, False, res.wire_bytes if res else 0, name)
                    return
                self._spend(res.wire_bytes)
                self.stats.pages_ok += 1
                self.label("http", url, True, res.wire_bytes, name)
                log.debug("GET %s %s %dB", url, res.status, res.wire_bytes)
                links = extract_links(res.html, url)
            candidates = [
                link for link in links
                if not is_blocked(link, safety["blocked_fragments"])
                and (not http["stay_on_persona_domains"] or host_allowed(link, persona["domains"]))
            ]
            url = self.rng.choice(candidates) if candidates else None
            if not self._sleep(self._uniform(sched["dwell_s"])):
                return

    def run_session(self) -> None:
        rotator = self.rotator
        if (self.locale_rotator and self.features.enabled("locale_packs")
                and self.rng.random() < float(self.options.get("locale_share", 0.6))):
            rotator = self.locale_rotator
        name, persona = rotator.pick(self.rng, self.drift_days())
        dns_cfg, http_cfg = self.cfg["dns"], self.cfg["http"]
        weights = [dns_cfg["weight"] if dns_cfg["enabled"] else 0.0,
                   http_cfg["weight"] if http_cfg["enabled"] else 0.0]
        kind = self.rng.choices(["dns", "http"], weights=weights, k=1)[0]
        self.stats.sessions += 1
        log.debug("session %d: %s/%s", self.stats.sessions, name, kind)
        if kind == "dns":
            self.dns_session(persona["domains"], name)
        else:
            self.http_session(persona, name)

    def run(self, once: bool = False) -> Stats:
        self.refresh_features()
        log.info("noisycompany started (preset=%s, personas=%s%s)", self.cfg["general"]["preset"],
                 ",".join(self.active_personas()), ", dry-run" if self.dry_run else "")
        gap = self.cfg["schedule"]["mean_session_gap_s"]
        try:
            while not self.stop.is_set():
                if not once and not self._sleep(self.rng.expovariate(1 / gap)):
                    break
                if not once and not self.wait_for_slot():
                    break
                self.run_session()
                self.save_stats()
                if once:
                    break
        finally:
            for srv in self.servers.values():
                srv.stop()
            self.state = "stopped"
            self.save_stats()
            log.info("noisycompany stopped: %s", self.stats)
        return self.stats
