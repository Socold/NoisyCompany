"""Command line interface."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from pathlib import Path

from noisycompany import __version__, config, impact
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
