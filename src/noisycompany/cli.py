"""Command line interface."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
import tomllib
from pathlib import Path

from noisycompany import (
    __version__,
    collective,
    companion,
    config,
    impact,
    packs,
    privacy,
    study,
)
from noisycompany.engine import Engine
from noisycompany.features import FEATURES, FeatureSet, NotAvailable, UnknownFeature


def _state_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "noisycompany"


def cmd_run(args: argparse.Namespace) -> int:
    cfg = config.load(args.config, args.preset)
    personas = config.load_personas(cfg)
    logging.basicConfig(level=args.log_level or cfg["general"]["log_level"],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if hasattr(os, "nice"):
        try:
            os.nice(cfg["general"]["nice"])
        except OSError:
            pass
    engine = Engine(cfg, personas, _state_dir(args.state_dir), dry_run=args.dry_run)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: engine.stop.set())
    engine.run(once=args.once)
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    cfg = config.load(args.config, args.preset)
    est = impact.estimate(cfg, args.grid)
    if args.json:
        print(json.dumps(est.__dict__, indent=2))
    else:
        print(f"preset: {cfg['general']['preset']}\n{est.as_text()}")
    return 0


def cmd_personas(args: argparse.Namespace) -> int:
    cfg = config.load(args.config, args.preset)
    for name, p in config.load_personas(cfg).items():
        print(f"{name:14} {len(p['seeds'])} seeds, {len(p['domains'])} domains: "
              + ", ".join(p["domains"]))
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    cfg = config.load(args.config, args.preset)
    fs = FeatureSet(cfg, _state_dir(args.state_dir))
    if args.action in ("on", "off"):
        if not args.feature:
            print("usage: noisycompany features on|off <id>", file=sys.stderr)
            return 2
        try:
            fs.set(args.feature, args.action == "on")
        except UnknownFeature:
            print(f"unknown feature {args.feature!r}", file=sys.stderr)
            return 2
        except NotAvailable as exc:
            print(f"not available yet: {exc}", file=sys.stderr)
            return 3
        print(f"{args.feature}: {args.action} (applies at the next session)")
        return 0
    width = max(len(f.id) for f in FEATURES)
    for f in fs.snapshot():
        state = ("ON " if f["enabled"] else "off") if f["available"] else "planned"
        print(f"{f['id']:<{width}}  {state:<7}  {f['milestone']:<8}  {f['title']}")
    return 0


def cmd_privacy(args: argparse.Namespace) -> int:
    cfg = config.load(args.config, args.preset)
    fs = FeatureSet(cfg, _state_dir(args.state_dir))
    report = privacy.build_report(Path.home(), {"doh_sink": fs.enabled("doh_sink"),
                                                "_running": _is_running(args.state_dir)})
    print(json.dumps(report.as_dict(), indent=2) if args.json else report.as_text())
    return 0


def _is_running(state_dir: str | None) -> bool:
    """noisycompany wrote stats.json in the last 15 minutes."""
    try:
        return time.time() - (_state_dir(state_dir) / "stats.json").stat().st_mtime < 900
    except OSError:
        return False


def cmd_packs(args: argparse.Namespace) -> int:
    state = _state_dir(args.state_dir)
    if args.action == "check":
        bad = 0
        for path in args.names:
            try:
                with open(path, "rb") as fh:
                    data = tomllib.load(fh)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                print(f"{path}: cannot read: {exc}")
                bad += 1
                continue
            problems = packs.validate(data, require_meta="meta" in data or not args.no_meta)
            for p in problems:
                print(f"{path}: {p}")
            bad += bool(problems)
            if not problems:
                print(f"{path}: ok")
        return 1 if bad else 0
    if args.action in ("install", "remove"):
        if not args.names:
            print(f"usage: noisycompany packs {args.action} <name>...", file=sys.stderr)
            return 2
        for name in args.names:
            if args.action == "install":
                packs.install(name, state)
                print(f"installed {name}")
            elif packs.remove(name, state):
                print(f"removed {name}")
            else:
                print(f"{name} is not installed", file=sys.stderr)
        print("(used when the persona_marketplace switch is on)")
        return 0
    inst = set(packs.installed(state))
    for name, data in packs.bundled().items():
        meta = data["meta"]
        mark = "installed" if name in inst else ""
        print(f"{name:16} {meta['lang']:3} {mark:10} {meta['title']}: {meta['description']}")
    return 0


def cmd_companion(args: argparse.Namespace) -> int:
    target = Path(args.dir)
    if not target.is_dir():
        print(f"{target} is not a directory", file=sys.stderr)
        return 2
    stale = companion.export(target, check=args.check)
    if args.check:
        if stale:
            print("stale companion files: " + ", ".join(stale)
                  + " (run `noisycompany companion export`)", file=sys.stderr)
            return 1
        print("companion files up to date")
        return 0
    print("written: " + (", ".join(stale) if stale else "nothing (already up to date)"))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Exit 0 when healthy. Used by Docker HEALTHCHECK and appliance supervisors."""
    cfg = config.load(args.config, args.preset)
    state = _state_dir(args.state_dir)
    if not FeatureSet(cfg, state).enabled("appliance_packages"):
        print("health file disabled (switch appliance_packages off)")
        return 0
    try:
        age = time.time() - (state / "health").stat().st_mtime
    except OSError:
        print("no health file yet", file=sys.stderr)
        return 1
    ok = age <= args.max_age
    print(f"{'healthy' if ok else 'stale'}: last heartbeat {age:.0f} s ago")
    return 0 if ok else 1


def cmd_collective(args: argparse.Namespace) -> int:
    state = _state_dir(args.state_dir)
    if args.action == "create":
        cfg = config.load(args.config, args.preset)
        names = args.personas.split(",") if args.personas else cfg["personas"]["enabled"]
        group = collective.create(args.name or "household", names, args.rotate_days,
                                  args.active_count)
        code = collective.encode(group)
        print(code)
        print("\nShare this code with the other members (it contains the shared secret).\n"
              "Each member runs: noisycompany collective join '<code>'\n"
              "then: noisycompany features on collective_noise", file=sys.stderr)
        if args.join:
            collective.join(code, state)
        return 0
    if args.action == "join":
        if not args.code:
            print("usage: noisycompany collective join <code|file>", file=sys.stderr)
            return 2
        code = Path(args.code).read_text().strip() if Path(args.code).is_file() else args.code
        group = collective.join(code, state)
        print(f"joined {group['name']!r}: {len(group['personas'])} personas, "
              f"{group['active_count']} active, rotation {group['rotate_days']} d")
        return 0
    if args.action == "leave":
        print("left the collective" if collective.leave(state) else "no collective joined")
        return 0
    group = collective.current(state)
    if not group:
        print("no collective joined")
        return 0
    print(f"{group['name']}: {', '.join(group['personas'])} "
          f"({group['active_count']} active, rotation {group['rotate_days']} d)")
    if args.code_out:
        print(collective.encode(group))
    return 0


def cmd_study(args: argparse.Namespace) -> int:
    noise = study.load_noise(Path(args.noise))
    human = study.load_trace(Path(args.human))
    if args.exclude_noise_hosts:
        # A DNS trace taken on the same network also contains the noise itself.
        noise_ts = {(round(e.ts), e.host) for e in noise}
        human = [e for e in human if (round(e.ts), e.host) not in noise_ts]
    res = study.run(noise, human, args.window, args.folds)
    if args.json:
        print(json.dumps(res.__dict__ | {"verdict": res.verdict()}, indent=2))
    else:
        print(res.as_text())
    return 0 if res.auc == res.auc else 1


def cmd_config(args: argparse.Namespace) -> int:
    if args.print_default:
        sys.stdout.write(config.default_text())
        return 0
    cfg = config.load(args.config, args.preset)
    print(json.dumps(cfg, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="noisycompany", description=__doc__)
    p.add_argument("--version", action="version", version=f"noisycompany {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", help="TOML config file")
    common.add_argument("-p", "--preset", choices=sorted(config.PRESETS))
    common.add_argument("--state-dir", help="where salt, switches and stats.json live")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", parents=[common], help="generate noise")
    r.add_argument("--dry-run", action="store_true", help="no network, log intended actions")
    r.add_argument("--once", action="store_true", help="run a single session then exit")
    r.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("estimate", parents=[common], help="bandwidth and energy estimate")
    e.add_argument("--grid", type=float, default=50.0,
                   help="grid carbon intensity gCO2e/kWh (default 50, ~France; EU ~250)")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_estimate)

    pe = sub.add_parser("personas", parents=[common], help="list enabled personas")
    pe.set_defaults(func=cmd_personas)

    f = sub.add_parser("features", parents=[common], help="list or switch features on/off")
    f.add_argument("action", nargs="?", choices=["list", "on", "off"], default="list")
    f.add_argument("feature", nargs="?")
    f.set_defaults(func=cmd_features)

    pr = sub.add_parser("privacy", parents=[common], help="local privacy report and score")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_privacy)

    pk = sub.add_parser("packs", parents=[common], help="persona packs: list, install, check")
    pk.add_argument("action", nargs="?", choices=["list", "install", "remove", "check"],
                    default="list")
    pk.add_argument("names", nargs="*")
    pk.add_argument("--no-meta", action="store_true", help="check: allow files without [meta]")
    pk.set_defaults(func=cmd_packs)

    co = sub.add_parser("companion", help="generate the browser companion's personas/manifest")
    co.add_argument("action", choices=["export"])
    co.add_argument("--dir", default="companion/src")
    co.add_argument("--check", action="store_true", help="fail if files are stale")
    co.set_defaults(func=cmd_companion)

    h = sub.add_parser("health", parents=[common], help="exit 0 if the daemon is alive")
    h.add_argument("--max-age", type=float, default=180,
                   help="seconds since the last heartbeat (default 180)")
    h.set_defaults(func=cmd_health)

    cl = sub.add_parser("collective", parents=[common],
                        help="shared decoy personas across households")
    cl.add_argument("action", nargs="?", choices=["show", "create", "join", "leave"],
                    default="show")
    cl.add_argument("code", nargs="?", help="join: share code or file")
    cl.add_argument("--name", help="create: collective name")
    cl.add_argument("--personas", help="create: comma-separated personas (default: enabled)")
    cl.add_argument("--rotate-days", type=int, default=10)
    cl.add_argument("--active-count", type=int, default=3)
    cl.add_argument("--join", action="store_true", help="create: also join it")
    cl.add_argument("--code-out", action="store_true", help="show: print the share code")
    cl.set_defaults(func=cmd_collective)

    st = sub.add_parser("study", parents=[common], help="how separable is the noise?")
    st.add_argument("--noise", required=True, help="labelled log (JSONL) from labelled_log")
    st.add_argument("--human", required=True, help="real trace: CSV or JSONL, time + domain")
    st.add_argument("--window", type=float, default=600, help="window width, seconds")
    st.add_argument("--folds", type=int, default=5)
    st.add_argument("--exclude-noise-hosts", action="store_true",
                    help="drop trace lines matching a noise event (same second + host)")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_study)

    c = sub.add_parser("config", parents=[common], help="show effective config")
    c.add_argument("--print-default", action="store_true")
    c.set_defaults(func=cmd_config)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config.ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
