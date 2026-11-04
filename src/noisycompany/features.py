"""Feature switches: every roadmap item has an on/off switch, off by default.

The effective state is: [features] table of the config file, then the runtime
overrides in <state_dir>/features.json (written by `noisycompany features on|off` and by
the dashboard buttons). The engine re-reads the overrides between sessions, so a switch
flipped in the dashboard applies without restart.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    description: str
    milestone: str
    available: bool  # False = planned: visible, cannot be switched on yet


FEATURES: tuple[Feature, ...] = (
    Feature("persona_drift", "Persona drift",
            "A main hobby stays for months; secondary interests rotate every few days.",
            "2.1", True),
    Feature("locale_packs", "Local persona packs",
            "Add personas in your language (French pack included) so decoys match your locale.",
            "2.1", True),
    Feature("metered_guard", "Metered connection guard",
            "On a metered link (NetworkManager), fall back to the eco budget automatically.",
            "2.1", True),
    Feature("doh_sink", "DNS noise over DoH",
            "Send DNS noise to the same DNS-over-HTTPS resolver your browser uses.",
            "2.2", True),
    Feature("metrics", "Prometheus metrics",
            "Expose counters on http://127.0.0.1:9789/metrics for home-lab dashboards.",
            "2.2", True),
    Feature("dashboard", "Local dashboard",
            "Web page on http://127.0.0.1:9788 with stats and on/off buttons for every feature.",
            "2.2", True),
    Feature("labelled_log", "Labelled ground-truth log",
            "Write every generated action to a JSONL file: benign traffic with ground truth "
            "for SOC / IDS / NDR detection testing.",
            "2.2", True),
    Feature("privacy_report", "Household privacy report",
            "Local checks (blocker, encrypted DNS, fingerprinting, GPC, IPv6 privacy, noise "
            "coherence) combined into a score, shown in the dashboard. Nothing is sent.",
            "2.3", True),
    Feature("browser_companion", "Browser companion",
            "Firefox WebExtension (companion/): rare persona visits from the real browser. "
            "Its switch lives in the extension popup; this one only records your choice.",
            "2.3", True),
    Feature("persona_marketplace", "Persona marketplace",
            "Reviewed persona packs shipped with the code, installable by name "
            "(`noisycompany packs`), validated in CI against sensitive topics.",
            "2.3", True),
    Feature("business_profiles", "Business traffic profiles",
            "Replace personas with a business profile (office, dev_team, retail) for SOC labs; "
            "the profile is written in the labelled log.",
            "2.4", True),
    Feature("appliance_packages", "Appliance packages",
            "Home Assistant add-on, docker-compose, Raspberry Pi and OpenWrt installers, "
            "multi-arch image. The switch writes a health file for `noisycompany health`.",
            "2.4", True),
    Feature("request_trees", "Realistic request trees",
            "Also fetch up to 3 same-origin CSS/JS files per page, once per URL like a browser "
            "cache, to look less like a bot. About +60 % bandwidth.",
            "3.0", True),
    Feature("collective_noise", "Collective noise",
            "Join a collective by share code: members rotate the same reviewed personas at "
            "the same time, so decoys are common to all. No server, no new domains.",
            "3.0", True),
    Feature("dns_coherence", "DNS follows reading",
            "DNS noise looks up the hosts of pages the persona actually read and the links "
            "it saw, like a browser revisiting, instead of independent lookups.",
            "2.2", True),
    Feature("weekly_rhythm", "Weekly rhythm",
            "Busier on evenings, later mornings on weekends and holidays, quieter in "
            "summer. Changes when sessions happen, never the daily cap.",
            "2.2", True),
    Feature("third_party_bursts", "Third-party host bursts",
            "After a page, resolve (DNS only, no download) a few of the other hosts it "
            "embeds, as a browser does. Ad and tracker hosts are skipped. ~300 B each.",
            "2.2", True),
    Feature("separability_study", "Separability study",
            "`noisycompany study`: classifier (ROC AUC) between the labelled log and a real "
            "DNS trace you export (Pi-hole...). Tells which features give the noise away.",
            "research", True),
)

BY_ID = {f.id: f for f in FEATURES}


class UnknownFeature(KeyError):
    pass


class NotAvailable(ValueError):
    pass


class FeatureSet:
    def __init__(self, cfg: dict[str, Any], state_dir: Path | None) -> None:
        self._base = {k: bool(v) for k, v in cfg.get("features", {}).items()
                      if not isinstance(v, dict)}
        self._path = state_dir / "features.json" if state_dir else None
        self._overrides: dict[str, bool] = {}
        self._mtime = -1.0
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        if not self._path:
            return
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            self._overrides, self._mtime = {}, -1.0
            return
        if mtime == self._mtime:
            return
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return
        with self._lock:
            self._overrides = {k: bool(v) for k, v in data.items() if k in BY_ID}
            self._mtime = mtime

    def enabled(self, feature_id: str) -> bool:
        if feature_id not in BY_ID:
            raise UnknownFeature(feature_id)
        if not BY_ID[feature_id].available:
            return False
        with self._lock:
            if feature_id in self._overrides:
                return self._overrides[feature_id]
        return self._base.get(feature_id, False)

    def set(self, feature_id: str, on: bool) -> None:
        if feature_id not in BY_ID:
            raise UnknownFeature(feature_id)
        if on and not BY_ID[feature_id].available:
            raise NotAvailable(f"{feature_id} is planned for {BY_ID[feature_id].milestone}")
        if not self._path:
            raise RuntimeError("no state directory: cannot persist switches")
        with self._lock:
            self._overrides[feature_id] = on
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._overrides, indent=2, sort_keys=True))
            os.replace(tmp, self._path)
            self._mtime = self._path.stat().st_mtime

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"id": f.id, "title": f.title, "description": f.description,
             "milestone": f.milestone, "available": f.available, "enabled": self.enabled(f.id)}
            for f in FEATURES
        ]
