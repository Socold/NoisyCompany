"""SOC test scenarios (feature `business_profiles` + `labelled_log`).

A scenario file names a business profile, a preset, a duration and switches. `noisycompany
scenario run <name>` produces its labelled benign traffic offline (simulated clock, no
network, see benchmark.py), then checks the properties detection engineers rely on:

- no periodicity a beaconing rule could catch (coefficient of variation of the gaps);
- the hourly action cap is respected;
- every record is labelled `benign-noise` with the scenario's profile.

Replay the JSONL into the SIEM / NDR under test: rules must stay quiet on it.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import tomllib
from collections import Counter
from importlib import resources
from pathlib import Path
from typing import Any

from noisycompany import benchmark, config, packs
from noisycompany.config import ConfigError


def available() -> dict[str, dict[str, Any]]:
    base = resources.files("noisycompany.data").joinpath("scenarios")
    out = {}
    for entry in base.iterdir():
        if entry.name.endswith(".toml"):
            out[entry.name[:-5]] = tomllib.loads(entry.read_text("utf-8"))["scenario"]
    return dict(sorted(out.items()))


def load(name_or_path: str) -> dict[str, Any]:
    path = Path(name_or_path)
    if path.suffix == ".toml" and path.is_file():
        sc = tomllib.loads(path.read_text("utf-8"))["scenario"]
    else:
        scs = available()
        if name_or_path not in scs:
            raise ConfigError(f"unknown scenario {name_or_path!r}; available: " + ", ".join(scs))
        sc = scs[name_or_path]
    if sc.get("profile") not in packs.business_profiles():
        names = ", ".join(packs.business_profiles())
        raise ConfigError(f"scenario profile must be one of: {names}")
    if not 1 <= int(sc.get("days", 7)) <= 60:
        raise ConfigError("scenario days must be in [1, 60]")
    return sc


def run(sc: dict[str, Any], out: Path, seed: int = 1) -> dict[str, Any]:
    cfg = config.load(preset=sc.get("preset", "eco"))
    if sc.get("active_hours"):
        cfg["schedule"]["active_hours"] = list(sc["active_hours"])
    switches = {"business_profiles": True} | dict(sc.get("switches", {}))
    benchmark.simulate_noise(switches, int(sc.get("days", 7)), seed, cfg=cfg,
                             options={"business_profile": sc["profile"]}, keep_log=out)
    return check(out, cfg["budget"]["max_actions_per_hour"], sc["profile"])


def check(log: Path, max_per_hour: int, profile: str) -> dict[str, Any]:
    recs = [json.loads(x) for x in log.read_text("utf-8").splitlines() if x.strip()]
    times = sorted(dt.datetime.fromisoformat(r["ts"]).timestamp() for r in recs)
    # Session starts: gaps above 5 minutes (inside a session, actions are seconds apart).
    starts = [b for a, b in zip(times, times[1:], strict=False) if b - a > 300]
    gaps = [b - a for a, b in zip(starts, starts[1:], strict=False)]
    cv = statistics.pstdev(gaps) / statistics.fmean(gaps) if len(gaps) > 2 else float("nan")
    per_hour = Counter(int(t // 3600) for t in times)
    return {
        "records": len(recs),
        "hosts": len({r["target"].split("/")[2] if "://" in r["target"] else r["target"]
                      for r in recs}),
        "session_gap_cv": round(cv, 2),
        "no_beaconing": cv > 0.5,  # periodic beacons have a CV close to 0
        "max_actions_in_an_hour": max(per_hour.values(), default=0),
        "hourly_cap_respected": max(per_hour.values(), default=0) <= max_per_hour,
        "all_labelled": all(r["label"] == "benign-noise" and r["profile"] == profile
                            for r in recs),
    }
