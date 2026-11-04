"""Household privacy report (feature `privacy_report`).

Local, read-only checks of what actually protects you against profiling, combined with
the noise state. Nothing is sent anywhere; the report contains booleans and advice,
never file paths or browsing data.

Checks are best effort and Linux-first (Firefox and Chromium-family profiles, systemd-
resolved). A check that cannot decide reports "unknown" and does not count.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # noqa: S404 - fixed argv, no shell
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

BLOCKER_IDS_FIREFOX = {
    "uBlock0@raymondhill.net": "uBlock Origin",
    "jid1-MnnxcxisBPnSXQ@jetpack": "Privacy Badger",
    "adnauseam@rednoise.org": "AdNauseam",
    "adguardadblocker@adguard.com": "AdGuard",
}
BLOCKER_IDS_CHROMIUM = {
    "cjpalhdlnbpafiamejdnhcphjbkeiagm": "uBlock Origin",
    "ddkjiahejlhfcafbddmgiahcphecmpfh": "uBlock Origin Lite",
    "pkehgijcmpdhfbdbbnkijodmdjhbjlgp": "Privacy Badger",
    "bgnkhhnnamicmpeenaelnjfhikgbkllg": "AdGuard",
}


@dataclass
class Check:
    id: str
    title: str
    status: str
    weight: int
    advice: str
    detail: str = ""


@dataclass
class Report:
    score: int | None
    checks: list[Check] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "checks": [asdict(c) for c in self.checks]}

    def as_text(self) -> str:
        icon = {PASS: "[ok]  ", FAIL: "[--]  ", UNKNOWN: "[??]  "}
        lines = [f"Privacy score: {self.score if self.score is not None else 'n/a'}/100", ""]
        for c in self.checks:
            lines.append(f"{icon[c.status]}{c.title}" + (f" ({c.detail})" if c.detail else ""))
            if c.status == FAIL:
                lines.append(f"      -> {c.advice}")
        lines.append("")
        lines.append("Local checks only. Nothing was sent anywhere.")
        return "\n".join(lines)


# ------------------------------------------------------------------ browser discovery
def firefox_profiles(home: Path) -> list[Path]:
    roots = [home / ".mozilla/firefox", home / ".config/mozilla/firefox",
             home / ".var/app/org.mozilla.firefox/.mozilla/firefox",
             home / "snap/firefox/common/.mozilla/firefox",
             home / "Library/Application Support/Firefox/Profiles"]
    out = []
    for root in roots:
        if root.is_dir():
            out += [p.parent for p in root.glob("*/prefs.js")]
    return out


def chromium_profiles(home: Path) -> list[Path]:
    roots = [home / ".config/google-chrome", home / ".config/chromium",
             home / ".config/BraveSoftware/Brave-Browser", home / ".config/vivaldi",
             home / ".var/app/com.google.Chrome/config/google-chrome",
             home / ".var/app/org.chromium.Chromium/config/chromium"]
    return [r for r in roots if (r / "Local State").is_file()]


_PREF = re.compile(r'user_pref\("([^"]+)",\s*(.+?)\);')


def read_prefs(profile: Path) -> dict[str, Any]:
    prefs: dict[str, Any] = {}
    for name in ("prefs.js", "user.js"):
        try:
            text = (profile / name).read_text(errors="replace")
        except OSError:
            continue
        for key, raw in _PREF.findall(text):
            try:
                prefs[key] = json.loads(raw)
            except ValueError:
                prefs[key] = raw
    return prefs


def firefox_extensions(profile: Path) -> set[str]:
    try:
        data = json.loads((profile / "extensions.json").read_text())
    except (OSError, ValueError):
        return set()
    return {a.get("id", "") for a in data.get("addons", []) if a.get("active")}


def chromium_extensions(root: Path) -> set[str]:
    ids: set[str] = set()
    for prof in root.iterdir() if root.is_dir() else []:
        ext = prof / "Extensions"
        if ext.is_dir():
            ids |= {p.name for p in ext.iterdir()}
    return ids


def chromium_doh(root: Path) -> bool | None:
    try:
        data = json.loads((root / "Local State").read_text())
    except (OSError, ValueError):
        return None
    mode = data.get("dns_over_https", {}).get("mode")
    return None if mode is None else mode == "secure"


# ------------------------------------------------------------------ system
def resolved_dot(runner: Callable[[], str] | None = None) -> bool | None:
    if runner is None:
        exe = shutil.which("resolvectl")
        if not exe:
            return None

        def runner() -> str:
            try:
                return subprocess.run([exe, "status"], capture_output=True, text=True,  # noqa: S603
                                      timeout=5, check=False).stdout
            except (OSError, subprocess.SubprocessError):
                return ""
    text = runner()
    if not text:
        return None
    return "+DNSOverTLS" in text or "DNSOverTLS=yes" in text


def ipv6_tempaddr(path: Path = Path("/proc/sys/net/ipv6/conf/all/use_tempaddr")) -> bool | None:
    try:
        return int(path.read_text().strip()) >= 1
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ report
def _status(value: bool | None) -> str:
    return UNKNOWN if value is None else (PASS if value else FAIL)


def _any(values: Iterable[bool | None]) -> bool | None:
    vals = [v for v in values if v is not None]
    return None if not vals else any(vals)


def build_report(home: Path, features: dict[str, bool] | None = None,
                 resolved: Callable[[], str] | None = None,
                 tempaddr_path: Path | None = None) -> Report:
    features = features or {}
    ff = firefox_profiles(home)
    cr = chromium_profiles(home)
    prefs = [read_prefs(p) for p in ff]
    browsers_found = bool(ff or cr)

    # Encrypted DNS: browser DoH (Firefox TRR mode 2/3, Chromium secure) or system DoT.
    ff_doh = [p.get("network.trr.mode") in (2, 3) for p in prefs] if prefs else []
    browser_doh = _any([*ff_doh, *(chromium_doh(r) for r in cr)])
    system_dot = resolved_dot(resolved)
    enc_dns = _any([browser_doh, system_dot])

    blockers: set[str] = set()
    for p in ff:
        blockers |= {BLOCKER_IDS_FIREFOX[i] for i in firefox_extensions(p)
                     if i in BLOCKER_IDS_FIREFOX}
    for r in cr:
        blockers |= {BLOCKER_IDS_CHROMIUM[i] for i in chromium_extensions(r)
                     if i in BLOCKER_IDS_CHROMIUM}

    fp = _any([bool(p.get("privacy.resistFingerprinting")
                    or p.get("privacy.fingerprintingProtection")
                    or p.get("browser.contentblocking.category") == "strict")
               for p in prefs]) if prefs else None
    gpc = _any([bool(p.get("privacy.globalprivacycontrol.enabled")) for p in prefs]) \
        if prefs else None
    temp = ipv6_tempaddr(tempaddr_path) if tempaddr_path else ipv6_tempaddr()

    noise_on = features.get("_running", False)
    # Coherence: if the browser uses DoH but noise uses plain DNS, noise is trivially split.
    coherent: bool | None = None
    if browser_doh is not None:
        coherent = (not browser_doh) or features.get("doh_sink", False)

    checks = [
        Check("blocker", "Content blocker in the browser", _status(
            bool(blockers) if browsers_found else None), 30,
            "Install uBlock Origin: it stops most targeted-ad tracking at the source.",
            ", ".join(sorted(blockers))),
        Check("encrypted_dns", "Encrypted DNS (DoH/DoT)", _status(enc_dns), 20,
              "Enable DNS over HTTPS in the browser (Firefox: Settings > Privacy > DNS over "
              "HTTPS, Max protection) or DNSOverTLS in systemd-resolved."),
        Check("fingerprinting", "Fingerprinting protection", _status(fp), 15,
              "Firefox: Enhanced Tracking Protection 'Strict', or use Mullvad/Tor Browser."),
        Check("gpc", "Global Privacy Control signal", _status(gpc), 5,
              "Firefox: set privacy.globalprivacycontrol.enabled = true (legal opt-out "
              "signal in several jurisdictions)."),
        Check("ipv6_privacy", "IPv6 temporary addresses", _status(temp), 10,
              "Set net.ipv6.conf.all.use_tempaddr = 2 so your IPv6 address does not "
              "identify the device over time."),
        Check("noise", "NoisyCompany running", _status(noise_on), 10,
              "Run `noisycompany run` (or the systemd unit) to dilute network-level profiles."),
        Check("noise_dns_coherence", "Noise DNS goes where browser DNS goes", _status(coherent),
              10, "The browser uses DoH: switch on `doh_sink` with the same resolver, otherwise "
              "DNS noise is easy to separate from real queries."),
    ]
    decided = [c for c in checks if c.status != UNKNOWN]
    total = sum(c.weight for c in decided)
    score = round(100 * sum(c.weight for c in decided if c.status == PASS) / total) \
        if total else None
    return Report(score, checks)
