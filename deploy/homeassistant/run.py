"""Home Assistant add-on entrypoint: /data/options.json -> TOML config -> noisycompany run.

Starts as root only to read the Supervisor's options and prepare /data/state, then drops
to an unprivileged user before running the daemon.
"""

import json
import os
import sys

OPTIONS = "/data/options.json"
STATE = "/data/state"
CONFIG = STATE + "/noisycompany.toml"
UID = GID = 10001  # the image's noisycompany user
# Files of add-on versions <= 2.0.1, which kept the state directly in /data.
LEGACY = ("salt", "features.json", "stats.json", "health", "labelled.jsonl",
          "labelled.jsonl.1", "collective.json", "packs", "noisycompany.toml")


def toml_list(values):
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def prepare_state() -> None:
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    for name in LEGACY:
        old, new = os.path.join("/data", name), os.path.join(STATE, name)
        if os.path.exists(old) and not os.path.exists(new):
            os.rename(old, new)


def chown_tree(root: str) -> None:
    if os.getuid() != 0:
        return
    os.chown(root, UID, GID)
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            os.chown(os.path.join(base, name), UID, GID, follow_symlinks=False)


def drop_privileges() -> None:
    if os.getuid() != 0:
        return
    os.setgroups([])
    os.setgid(GID)
    os.setuid(UID)
    if os.getuid() != UID or os.geteuid() != UID:
        raise SystemExit("could not drop privileges")


def main() -> int:
    with open(OPTIONS, encoding="utf-8") as fh:
        o = json.load(fh)
    lines = [
        "[general]", f"preset = {json.dumps(o['preset'])}",
        "[budget]", f"daily_mb = {float(o['daily_mb'])}",
        "[schedule]", f"active_hours = {toml_list(o['active_hours'])}",
        "[features]",
        "appliance_packages = true",
        f"locale_packs = {str(bool(o['locale_packs'])).lower()}",
        f"doh_sink = {str(bool(o['doh_sink'])).lower()}",
        f"privacy_report = {str(bool(o['privacy_report'])).lower()}",
    ]
    prepare_state()
    with open(CONFIG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    chown_tree(STATE)
    drop_privileges()
    os.execvp("noisycompany", ["noisycompany", "run", "-c", CONFIG, "--state-dir", STATE])  # noqa: S606,S607
    return 1


if __name__ == "__main__":
    sys.exit(main())
