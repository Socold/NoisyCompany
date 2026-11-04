"""Reviewed persona packs (feature `persona_marketplace`).

A pack is a TOML file with a [meta] table and one or more personas. Packs shipped in
data/packs/ are reviewed in pull requests and validated in CI by `noisycompany packs check`.
Installing copies a bundled pack into <state_dir>/packs/; nothing is downloaded, so a
pack cannot change behind the user's back.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from noisycompany.config import ConfigError

NAME_RE = re.compile(r"^[a-z0-9_]{2,40}$")

# Topics that could hurt the user if an observer believed them.
# STEMS match word prefixes (politic -> political), WORDS match whole words only
# (so "bet" does not hit "between", "pari" does not hit "Paris").
STEMS = [
    "medical", "médical", "disease", "cancer", "diabet", "depress", "dépress", "pregnan",
    "abortion", "avortement", "fertilit", "addiction", "maladie", "grossesse",
    "porn", "escort", "lgbt", "lesbian", "religio", "synagog", "mosque", "mosquée",
    "christian", "islam", "politic", "politique", "élection", "election", "crimin",
    "firearm", "cannabis", "gambl", "casino", "bankrupt", "payday", "torrent", "warez",
    "paris sportif",
]
WORDS = [
    "health", "santé", "hiv", "therapy", "rehab", "sex", "dating", "rencontres", "gay",
    "church", "église", "bible", "quran", "coran", "jewish", "party", "campaign", "crime",
    "weapon", "weapons", "gun", "guns", "arme", "armes", "drug", "drugs", "drogue", "drogues",
    "bet", "bets", "betting", "loan", "loans", "debt", "debts", "dette", "dettes", "crédit",
    "pirate", "piracy", "xxx", "adult", "crimes",
]
_SENSITIVE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in STEMS) + r")"
    r"|\b(" + "|".join(re.escape(w) for w in WORDS) + r")s?\b",
    re.IGNORECASE,
)
BLOCKED = ["login", "signin", "account", "checkout", "payment", "/ads", "doubleclick"]


def validate(data: dict[str, Any], require_meta: bool = True) -> list[str]:
    """Return the list of problems in a pack (empty = valid)."""
    errors: list[str] = []
    meta = data.get("meta")
    if require_meta:
        if not isinstance(meta, dict):
            return ["missing [meta] table"]
        for key in ("title", "lang", "description"):
            if not isinstance(meta.get(key), str) or not meta[key].strip():
                errors.append(f"[meta] {key} must be a non-empty string")
        if not isinstance(meta.get("version"), int):
            errors.append("[meta] version must be an integer")
    personas = {k: v for k, v in data.items() if k != "meta"}
    if not personas:
        errors.append("pack defines no persona")
    for name, p in personas.items():
        where = f"persona {name!r}"
        if not NAME_RE.match(name):
            errors.append(f"{where}: name must match {NAME_RE.pattern}")
        if not isinstance(p, dict):
            errors.append(f"{where}: must be a table")
            continue
        seeds, domains, queries = p.get("seeds"), p.get("domains"), p.get("queries")
        if not isinstance(seeds, list) or len(seeds) < 3:
            errors.append(f"{where}: at least 3 seeds")
            seeds = []
        if not isinstance(domains, list) or not domains:
            errors.append(f"{where}: at least 1 domain")
            domains = []
        if not isinstance(queries, list) or len(queries) < 5:
            errors.append(f"{where}: at least 5 queries")
            queries = []
        for s in seeds:
            if not isinstance(s, str) or not s.startswith("https://"):
                errors.append(f"{where}: seed {s!r} must be an https URL")
                continue
            host = s.split("/")[2].lower()
            if not any(host == d or host.endswith("." + d) for d in domains):
                errors.append(f"{where}: seed host {host!r} not in domains")
        for d in domains:
            if not isinstance(d, str) or "/" in d or ":" in d or "." not in d:
                errors.append(f"{where}: domain {d!r} must be a bare hostname")
        for text in [name, *map(str, seeds), *map(str, domains), *map(str, queries)]:
            m = _SENSITIVE_RE.search(text)
            if m:
                errors.append(f"{where}: sensitive topic {m.group(0)!r} in {text!r}")
            if any(b in text.lower() for b in BLOCKED):
                errors.append(f"{where}: blocked fragment in {text!r}")
    return errors


def _bundled_dir():
    return resources.files("noisycompany.data").joinpath("packs")


def bundled() -> dict[str, dict[str, Any]]:
    out = {}
    for entry in _bundled_dir().iterdir():
        if entry.name.endswith(".toml"):
            out[entry.name[:-5]] = tomllib.loads(entry.read_text("utf-8"))
    return dict(sorted(out.items()))


def installed_dir(state_dir: Path) -> Path:
    return state_dir / "packs"


def installed(state_dir: Path | None) -> list[str]:
    if not state_dir or not installed_dir(state_dir).is_dir():
        return []
    return sorted(p.stem for p in installed_dir(state_dir).glob("*.toml"))


def install(name: str, state_dir: Path) -> None:
    packs = bundled()
    if name not in packs:
        raise ConfigError(f"unknown pack {name!r}; available: {', '.join(packs)}")
    problems = validate(packs[name])
    if problems:
        raise ConfigError(f"pack {name!r} is invalid: {problems[0]}")
    target = installed_dir(state_dir)
    target.mkdir(parents=True, exist_ok=True)
    with resources.as_file(_bundled_dir().joinpath(f"{name}.toml")) as src:
        shutil.copyfile(src, target / f"{name}.toml")


def remove(name: str, state_dir: Path) -> bool:
    path = installed_dir(state_dir) / f"{name}.toml"
    if not NAME_RE.match(name) or not path.exists():
        return False
    path.unlink()
    return True


def installed_personas(state_dir: Path | None) -> dict[str, dict[str, list[str]]]:
    """Personas of installed packs. Invalid or tampered packs are skipped."""
    out: dict[str, dict[str, list[str]]] = {}
    for name in installed(state_dir):
        try:
            data = tomllib.loads((installed_dir(state_dir) / f"{name}.toml").read_text("utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if validate(data):
            continue
        out.update({k: v for k, v in data.items() if k != "meta"})
    return out


def signature(state_dir: Path | None) -> tuple[str, ...]:
    return tuple(installed(state_dir))
