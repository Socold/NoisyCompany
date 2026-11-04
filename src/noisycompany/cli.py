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
    pcapstudy,
    privacy,
    study,
)
from noisycompany.engine import Engine
from noisycompany.features import FEATURES, FeatureSet, NotAvailable, UnknownFeature
from noisycompany.i18n import _


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
            print(_("usage: noisycompany features on|off <id>"), file=sys.stderr)
            return 2
        try:
            fs.set(args.feature, args.action == "on")
        except UnknownFeature:
            print(_("unknown feature {f!r}").format(f=args.feature), file=sys.stderr)
            return 2
        except NotAvailable as exc:
            print(_("not available yet: {e}").format(e=exc), file=sys.stderr)
            return 3
        print(_("{f}: {a} (applies at the next session)").format(f=args.feature, a=args.action))
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
                print(_("installed {n}").format(n=name))
            elif packs.remove(name, state):
                print(_("removed {n}").format(n=name))
            else:
                print(_("{n} is not installed").format(n=name), file=sys.stderr)
        print(_("(used when the persona_marketplace switch is on)"))
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
        print(_("{t} is not a directory").format(t=target), file=sys.stderr)
        return 2
    stale = companion.export(target, check=args.check)
    if args.check:
        if stale:
            print("stale companion files: " + ", ".join(stale)
                  + " (run `noisycompany companion export`)", file=sys.stderr)
            return 1
        print(_("companion files up to date"))
        return 0
    print("written: " + (", ".join(stale) if stale else "nothing (already up to date)"))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Exit 0 when healthy. Used by Docker HEALTHCHECK and appliance supervisors."""
    cfg = config.load(args.config, args.preset)
    state = _state_dir(args.state_dir)
    if not FeatureSet(cfg, state).enabled("appliance_packages"):
        print(_("health file disabled (switch appliance_packages off)"))
        return 0
    try:
        age = time.time() - (state / "health").stat().st_mtime
    except OSError:
        print(_("no health file yet"), file=sys.stderr)
        return 1
    ok = age <= args.max_age
    msg = "healthy: last heartbeat {s:.0f} s ago" if ok else "stale: last heartbeat {s:.0f} s ago"
    print(_(msg).format(s=age))
    return 0 if ok else 1


def cmd_collective(args: argparse.Namespace) -> int:
    state = _state_dir(args.state_dir)
    if args.action == "create":
        cfg = config.load(args.config, args.preset)
        names = args.personas.split(",") if args.personas else cfg["personas"]["enabled"]
        group = collective.create(args.name or "household", names, args.rotate_days,
                                  min(args.active_count, len(set(names))), _expiry(args))
        code = collective.encode(group)
        print(code)
        if args.qr:
            _print_qr(code, args.svg)
        print("\nShare this code with the other members (it contains the shared secret).\n"
              "Each member runs: noisycompany collective join '<code>'\n"
              "then: noisycompany features on collective_noise", file=sys.stderr)
        if args.join:
            collective.join(code, state)
        return 0
    if args.action == "join":
        if not args.code:
            print(_("usage: noisycompany collective join <code|file>"), file=sys.stderr)
            return 2
        code = args.code if args.code.startswith(collective.PREFIX) \
            else Path(args.code).read_text().strip()
        group = collective.join(code, state)
        print(f"joined {group['name']!r}: {len(group['personas'])} personas, "
              f"{group['active_count']} active, rotation {group['rotate_days']} d")
        return 0
    if args.action in ("qr", "rotate"):
        try:
            group = json.loads((state / "collective.json").read_text())
            group = collective.decode(collective.encode(group))
        except (OSError, ValueError, config.ConfigError):
            print(_("no collective joined"), file=sys.stderr)
            return 1
        if args.action == "rotate":
            group = collective.rotate(group, _expiry(args))
            collective.join(collective.encode(group), state)
            print("new shared salt: send the new code to every member, the old one no "
                  "longer matches your rotation", file=sys.stderr)
        code = collective.encode(group)
        print(code)
        _print_qr(code, args.svg)
        return 0
    if args.action == "leave":
        print(_("left the collective") if collective.leave(state) else _("no collective joined"))
        return 0
    group = collective.current(state)
    if not group:
        raw = state / "collective.json"
        print("collective expired: ask for a new code (collective rotate)" if raw.exists()
              else "no collective joined")
        return 0
    print(f"{group['name']}: {', '.join(group['personas'])} "
          f"({group['active_count']} active, rotation {group['rotate_days']} d)")
    if args.code_out:
        print(collective.encode(group))
    return 0


def _expiry(args: argparse.Namespace):
    import datetime as dt
    return dt.date.today() + dt.timedelta(days=args.expires_days) if args.expires_days else None


def _print_qr(code: str, svg: str | None) -> None:
    from noisycompany import qr
    q = qr.encode(code)
    if svg:
        Path(svg).write_text(q.to_svg())
        print(_("QR code written to {p}").format(p=svg), file=sys.stderr)
    else:
        print(q.to_text(), file=sys.stderr)


def cmd_energy(args: argparse.Namespace) -> int:
    from noisycompany import energy, impact
    cfg = config.load(args.config, args.preset)
    eng = Engine(cfg, config.load_personas(cfg), None, dry_run=args.dry_run)
    eng.refresh_features()
    eng._sleep = lambda s: not eng.stop.is_set()  # sessions back to back, no dwell
    if energy.read_rapl_uj() is None:
        print("RAPL energy counters not readable (run as root for joules); "
              "CPU time only.", file=sys.stderr)
    m = energy.measure(eng.run_session, args.sessions)
    per_day = impact.estimate(cfg).sessions_per_day
    print(f"Sessions measured   : {m.sessions} in {m.seconds:.0f} s"
          + (" (dry run, no network)" if args.dry_run else ""))
    print(f"CPU time            : {m.cpu_s:.2f} s, {m.cpu_s / max(m.sessions, 1) * 1000:.0f} ms"
          " per session")
    if m.joules_per_session is not None:
        print(f"Package energy      : {m.joules_run:.1f} J run, {m.joules_idle:.1f} J idle "
              f"-> {m.joules_per_session:.2f} J per session")
        print(f"Per day ({per_day:.0f} sessions): {m.wh_per_day(per_day):.3f} Wh "
              "(CPU package, above idle)")
    return 0


def cmd_scenario(args: argparse.Namespace) -> int:
    from noisycompany import scenarios
    if args.action == "list" or not args.name:
        for name, sc in scenarios.available().items():
            print(f"{name:20} {sc['profile']:14} {sc.get('days', 7):>3} d  {sc['description']}")
        return 0
    sc = scenarios.load(args.name)
    out = Path(args.out)
    result = scenarios.run(sc, out, args.seed)
    print(f"{out}: {result['records']} labelled records, {result['hosts']} hosts")
    ok = True
    for key in ("no_beaconing", "hourly_cap_respected", "all_labelled"):
        ok &= result[key]
        print(f"  [{'ok' if result[key] else '!!'}] {key}")
    print(f"  session gap CV {result['session_gap_cv']}, "
          f"max {result['max_actions_in_an_hour']} actions in an hour")
    return 0 if ok else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    from noisycompany import __version__, benchmark
    rows = list(benchmark.run(args.days, args.seed))
    print(benchmark.as_json(rows) if args.json
          else benchmark.as_markdown(rows, args.days, args.seed, __version__))
    return 0


def cmd_study(args: argparse.Namespace) -> int:
    noise = study.load_noise(Path(args.noise))
    if args.pcap:
        try:
            res = pcapstudy.run(Path(args.pcap), noise, args.folds)
        except pcapstudy.PcapError as exc:
            print(f"{args.pcap}: {exc}", file=sys.stderr)
            return 2
    elif not args.human:
        print(_("study needs --human or --pcap"), file=sys.stderr)
        return 2
    if args.pcap:
        print(json.dumps(res.__dict__ | {"verdict": res.verdict()}, indent=2) if args.json
              else _("TLS flows, not DNS windows:") + "\n" + res.as_text())
        return 0 if res.auc == res.auc else 1
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
    common.add_argument("-c", "--config", help=_("TOML config file"))
    common.add_argument("-p", "--preset", choices=sorted(config.PRESETS))
    common.add_argument("--state-dir", help=_("where salt, switches and stats.json live"))
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", parents=[common], help=_("generate noise"))
    r.add_argument("--dry-run", action="store_true", help=_("no network, log intended actions"))
    r.add_argument("--once", action="store_true", help=_("run a single session then exit"))
    r.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("estimate", parents=[common], help=_("bandwidth and energy estimate"))
    e.add_argument("--grid", type=float, default=50.0,
                   help=_("grid carbon intensity gCO2e/kWh (default 50, ~France; EU ~250)"))
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_estimate)

    pe = sub.add_parser("personas", parents=[common], help=_("list enabled personas"))
    pe.set_defaults(func=cmd_personas)

    f = sub.add_parser("features", parents=[common], help=_("list or switch features on/off"))
    f.add_argument("action", nargs="?", choices=["list", "on", "off"], default="list")
    f.add_argument("feature", nargs="?")
    f.set_defaults(func=cmd_features)

    pr = sub.add_parser("privacy", parents=[common], help=_("local privacy report and score"))
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_privacy)

    pk = sub.add_parser("packs", parents=[common], help=_("persona packs: list, install, check"))
    pk.add_argument("action", nargs="?", choices=["list", "install", "remove", "check"],
                    default="list")
    pk.add_argument("names", nargs="*")
    pk.add_argument("--no-meta", action="store_true", help=_("check: allow files without [meta]"))
    pk.set_defaults(func=cmd_packs)

    co = sub.add_parser("companion", help=_("generate the browser companion's personas/manifest"))
    co.add_argument("action", choices=["export"])
    co.add_argument("--dir", default="companion/src")
    co.add_argument("--check", action="store_true", help=_("fail if files are stale"))
    co.set_defaults(func=cmd_companion)

    h = sub.add_parser("health", parents=[common], help=_("exit 0 if the daemon is alive"))
    h.add_argument("--max-age", type=float, default=180,
                   help=_("seconds since the last heartbeat (default 180)"))
    h.set_defaults(func=cmd_health)

    cl = sub.add_parser("collective", parents=[common],
                        help=_("shared decoy personas across households"))
    cl.add_argument("action", nargs="?",
                    choices=["show", "create", "join", "leave", "qr", "rotate"],
                    default="show")
    cl.add_argument("code", nargs="?", help=_("join: share code or file"))
    cl.add_argument("--name", help=_("create: collective name"))
    cl.add_argument("--personas", help=_("create: comma-separated personas (default: enabled)"))
    cl.add_argument("--rotate-days", type=int, default=10)
    cl.add_argument("--active-count", type=int, default=3)
    cl.add_argument("--join", action="store_true", help=_("create: also join it"))
    cl.add_argument("--code-out", action="store_true", help=_("show: print the share code"))
    cl.add_argument("--expires-days", type=int, default=0,
                    help=_("create/rotate: code valid this many days (0 = no expiry)"))
    cl.add_argument("--qr", action="store_true", help=_("create: also print a QR code"))
    cl.add_argument("--svg", help=_("qr/rotate/create: write the QR code to this SVG file"))
    cl.set_defaults(func=cmd_collective)

    en = sub.add_parser("energy", parents=[common],
                        help=_("measure CPU time and RAPL energy of real sessions"))
    en.add_argument("--sessions", type=int, default=20)
    en.add_argument("--dry-run", action="store_true", help=_("no network (CPU cost only)"))
    en.set_defaults(func=cmd_energy)

    sc = sub.add_parser("scenario", parents=[common],
                        help=_("SOC test scenarios: labelled benign traffic, offline"))
    sc.add_argument("action", nargs="?", choices=["list", "run"], default="list")
    sc.add_argument("name", nargs="?", help=_("run: scenario name or .toml file"))
    sc.add_argument("--out", default="scenario.jsonl", help=_("run: labelled JSONL output"))
    sc.add_argument("--seed", type=int, default=1)
    sc.set_defaults(func=cmd_scenario)

    bm = sub.add_parser("benchmark", parents=[common],
                        help=_("offline separability benchmark on simulated days"))
    bm.add_argument("--days", type=int, default=14)
    bm.add_argument("--seed", type=int, default=7)
    bm.add_argument("--json", action="store_true")
    bm.set_defaults(func=cmd_benchmark)

    st = sub.add_parser("study", parents=[common], help=_("how separable is the noise?"))
    st.add_argument("--noise", required=True, help=_("labelled log (JSONL) from labelled_log"))
    st.add_argument("--human", help=_("real trace: CSV or JSONL, time + domain"))
    st.add_argument("--pcap", help=_("packet capture (pcap/pcapng): study TLS flows instead"))
    st.add_argument("--window", type=float, default=600, help=_("window width, seconds"))
    st.add_argument("--folds", type=int, default=5)
    st.add_argument("--exclude-noise-hosts", action="store_true",
                    help=_("drop trace lines matching a noise event (same second + host)"))
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_study)

    c = sub.add_parser("config", parents=[common], help=_("show effective config"))
    c.add_argument("--print-default", action="store_true")
    c.set_defaults(func=cmd_config)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # State (salt, collective secret, stats, labelled log) is private to the user.
    os.umask(0o077)
    try:
        return args.func(args)
    except config.ConfigError as exc:
        print(_("config error: {e}").format(e=exc), file=sys.stderr)
        return 2
