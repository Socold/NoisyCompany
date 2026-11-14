"""Lightweight health check, kept apart from the CLI on purpose.

The Docker HEALTHCHECK runs it under the container's CPU cap (``cpus: 0.1``):
the full CLI (argparse, engine, study...) takes 25-30 s of wall time there,
this module about half (interpreter startup dominates). It only imports what
the check needs.

    python -m noisycompany.health [--max-age SECONDS] [--state-dir DIR]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from noisycompany import config
from noisycompany.features import FeatureSet
from noisycompany.i18n import _


def state_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "noisycompany"


def check(cfg_path: str | None, preset: str | None, state_arg: str | None,
          max_age: float) -> int:
    """Exit 0 when healthy. Used by Docker HEALTHCHECK and appliance supervisors."""
    cfg = config.load(cfg_path, preset)
    state = state_dir(state_arg)
    if not FeatureSet(cfg, state).enabled("appliance_packages"):
        print(_("health file disabled (switch appliance_packages off)"))
        return 0
    try:
        age = time.time() - (state / "health").stat().st_mtime
    except OSError:
        print(_("no health file yet"), file=sys.stderr)
        return 1
    ok = age <= max_age
    msg = "healthy: last heartbeat {s:.0f} s ago" if ok else "stale: last heartbeat {s:.0f} s ago"
    print(_(msg).format(s=age))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    opts = {"--max-age": "180", "--state-dir": None, "-c": None, "-p": None}
    while args:
        key = args.pop(0)
        if key not in opts or not args:
            print("usage: python -m noisycompany.health [--max-age S] [--state-dir DIR]"
                  " [-c CONFIG] [-p PRESET]", file=sys.stderr)
            return 2
        opts[key] = args.pop(0)
    return check(opts["-c"], opts["-p"], opts["--state-dir"], float(opts["--max-age"]))


if __name__ == "__main__":
    sys.exit(main())
