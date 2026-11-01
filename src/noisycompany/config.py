"""Configuration loading, presets and validation."""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    # ~3 MB/day: DNS-heavy, very few pages. For metered or slow links.
    "eco": {
        "budget": {"daily_mb": 3, "max_response_kb": 96, "max_actions_per_hour": 30},
        "schedule": {"mean_session_gap_s": 600, "pages_per_session": [1, 2]},
        "dns": {"weight": 0.75},
        "http": {"weight": 0.25},
    },
    "balanced": {},
    # ~60 MB/day: denser noise, still far below one minute of HD video per hour.
    "max": {
        "budget": {"daily_mb": 60, "max_response_kb": 384, "max_actions_per_hour": 240},
        "schedule": {"mean_session_gap_s": 90, "pages_per_session": [2, 8]},
        "personas": {"active_count": 5},
    },
}


class ConfigError(ValueError):
    """Raised when the configuration is invalid."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def default_text() -> str:
    return resources.files("noisycompany.data").joinpath("default.toml").read_text("utf-8")


def builtin_personas() -> dict[str, dict[str, list[str]]]:
    text = resources.files("noisycompany.data").joinpath("personas.toml").read_text("utf-8")
    return tomllib.loads(text)


@dataclass(frozen=True)
class TimeRange:
    start_min: int
    end_min: int

    @classmethod
    def parse(cls, text: str) -> TimeRange:
        try:
            a, b = text.split("-")
            ha, ma = (int(x) for x in a.strip().split(":"))
            hb, mb = (int(x) for x in b.strip().split(":"))
        except ValueError as exc:
            raise ConfigError(f"invalid time range {text!r}, expected HH:MM-HH:MM") from exc
        if not (0 <= ha <= 24 and 0 <= hb <= 24 and 0 <= ma < 60 and 0 <= mb < 60):
            raise ConfigError(f"invalid time range {text!r}")
        return cls(ha * 60 + ma, hb * 60 + mb)

    def contains(self, minute_of_day: int) -> bool:
        if self.start_min <= self.end_min:
            return self.start_min <= minute_of_day < self.end_min
        return minute_of_day >= self.start_min or minute_of_day < self.end_min  # spans midnight


def load(path: str | Path | None = None, preset: str | None = None) -> dict[str, Any]:
    """Return the effective config: defaults <- preset <- user file."""
    defaults = tomllib.loads(default_text())
    user: dict[str, Any] = {}
    if path:
        with open(path, "rb") as fh:
            user = tomllib.load(fh)
    chosen = preset or user.get("general", {}).get("preset") or defaults["general"]["preset"]
    if chosen not in PRESETS:
        raise ConfigError(f"unknown preset {chosen!r}, choose among {sorted(PRESETS)}")
    cfg = _deep_merge(_deep_merge(defaults, PRESETS[chosen]), user)
    cfg["general"]["preset"] = chosen
    validate(cfg)
    return cfg


def _pair(cfg: dict[str, Any], section: str, key: str) -> None:
    value = cfg[section][key]
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(v, int | float) for v in value)
        or value[0] < 0
        or value[0] > value[1]
    ):
        raise ConfigError(f"[{section}] {key} must be [min, max] with 0 <= min <= max")


def validate(cfg: dict[str, Any]) -> None:
    b = cfg["budget"]
    if not 0 < b["daily_mb"] <= 2048:
        raise ConfigError("[budget] daily_mb must be in (0, 2048]")
    if not 1 <= b["max_response_kb"] <= 4096:
        raise ConfigError("[budget] max_response_kb must be in [1, 4096]")
    if not 1 <= b["max_actions_per_hour"] <= 3600:
        raise ConfigError("[budget] max_actions_per_hour must be in [1, 3600]")
    for r in cfg["schedule"]["active_hours"]:
        TimeRange.parse(r)
    if cfg["schedule"]["mean_session_gap_s"] < 5:
        raise ConfigError("[schedule] mean_session_gap_s must be >= 5")
    for section, key in (("schedule", "pages_per_session"), ("schedule", "dwell_s"),
                         ("dns", "lookups_per_session")):
        _pair(cfg, section, key)
    if not (cfg["dns"]["enabled"] or cfg["http"]["enabled"]):
        raise ConfigError("at least one of [dns] or [http] must be enabled")
    if cfg["http"]["per_host_delay_s"] < 1:
        raise ConfigError("[http] per_host_delay_s must be >= 1")
    if not 0 <= cfg["general"]["nice"] <= 19:
        raise ConfigError("[general] nice must be in [0, 19]")
    doh_url = cfg.get("features", {}).get("options", {}).get("doh_url", "")
    if doh_url and not str(doh_url).startswith("https://"):
        raise ConfigError("[features.options] doh_url must be an https:// URL")
    if cfg["personas"]["active_count"] < 1:
        raise ConfigError("[personas] active_count must be >= 1")


def load_locale_personas(cfg: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """Personas of the locale packs listed in [features.options] locale_packs."""
    out: dict[str, dict[str, list[str]]] = {}
    packs = cfg.get("features", {}).get("options", {}).get("locale_packs", [])
    for lang in packs:
        if not str(lang).isalnum():
            raise ConfigError(f"invalid locale pack {lang!r}")
        try:
            text = resources.files("noisycompany.data").joinpath(
                f"personas_{lang}.toml").read_text("utf-8")
        except FileNotFoundError as exc:
            raise ConfigError(f"no persona pack for locale {lang!r}") from exc
        out.update(tomllib.loads(text))
    return out


def load_personas(cfg: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    personas = builtin_personas()
    extra = cfg["personas"].get("extra_file")
    if extra:
        with open(extra, "rb") as fh:
            personas.update(tomllib.load(fh))
    wanted = cfg["personas"]["enabled"]
    unknown = [p for p in wanted if p not in personas]
    if unknown:
        raise ConfigError(f"unknown personas: {unknown}")
    selected = {name: personas[name] for name in wanted}
    for name, p in selected.items():
        for field in ("seeds", "domains", "queries"):
            if not isinstance(p.get(field), list) or not p[field]:
                raise ConfigError(f"persona {name!r}: {field!r} must be a non-empty list")
    if not selected:
        raise ConfigError("[personas] enabled is empty")
    return selected
