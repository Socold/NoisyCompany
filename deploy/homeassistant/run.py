"""Home Assistant add-on entrypoint: /data/options.json -> TOML config -> noisycompany run."""

import json
import os
import sys

OPTIONS = "/data/options.json"
CONFIG = "/data/noisycompany.toml"


def toml_list(values):
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


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
    with open(CONFIG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.execvp("noisycompany", ["noisycompany", "run", "-c", CONFIG, "--state-dir", "/data"])  # noqa: S606,S607
    return 1


if __name__ == "__main__":
    sys.exit(main())
