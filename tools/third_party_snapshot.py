"""Maintainer tool: record which hosts a real browser contacts when it opens each persona page.

Same idea as HTTP Archive's crawl, at the scale of NoisyCompany's own seed pages: a
headless Chromium loads every persona seed URL once and notes each hostname requested,
in order, with its delay after navigation start. JavaScript-loaded hosts are included,
which the daemon cannot see in raw HTML. Trackers and ad hosts are dropped (the daemon
never looks them up). The result ships as data/third_parties.json; users install
nothing. Run by the monthly `third-parties` workflow, or by hand:

    pip install playwright==1.55.0 && playwright install chromium
    python tools/third_party_snapshot.py src/noisycompany/data/third_parties.json

Not part of the package: Playwright is a maintainer dependency only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import sys
import time
import tomllib
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from noisycompany.web import TRACKER_FRAGMENTS  # noqa: E402

MAX_HOSTS = 40
# Analytics beacons not caught by the daemon's own tracker list.
EXTRA_TRACKERS = ("insights",)
SETTLE_MS = 8000


def seed_urls() -> list[str]:
    files = sorted(glob.glob(str(ROOT / "src/noisycompany/data/personas*.toml"))
                   + glob.glob(str(ROOT / "src/noisycompany/data/packs/*.toml")))
    seeds: set[str] = set()
    for f in files:
        with open(f, "rb") as fh:
            for value in tomllib.load(fh).values():
                if isinstance(value, dict):
                    seeds.update(value.get("seeds", []))
                    # DNS noise opens the persona domains themselves: record their home page.
                    seeds.update(f"https://{d.strip().lower().rstrip('.')}/"
                                 for d in value.get("domains", []))
    return sorted(s for s in seeds if s.startswith("https://"))


def keep(host: str, page_host: str, blocked: list[str]) -> bool:
    return (bool(host) and host != page_host and "." in host
            and not any(f in host for f in TRACKER_FRAGMENTS)
            and not any(f in host for f in EXTRA_TRACKERS)
            and not any(f.strip("/") in host for f in blocked if f.startswith(("ad", "/ad"))))


def snapshot(urls: list[str], user_agent: str) -> dict[str, list[list]]:
    from playwright.sync_api import sync_playwright

    blocked = ["doubleclick", "googlesyndication", "adservice"]
    sites: dict[str, list[list]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for url in urls:
            page_host = (urllib.parse.urlsplit(url).hostname or "").lower()
            seen: dict[str, int] = {}
            ctx = browser.new_context(user_agent=user_agent, locale="en-US")
            page = ctx.new_page()
            t0 = time.monotonic()

            def on_request(req, seen=seen, t0=t0, page_host=page_host):
                host = (urllib.parse.urlsplit(req.url).hostname or "").lower()
                if host not in seen and keep(host, page_host, blocked):
                    seen[host] = int((time.monotonic() - t0) * 1000)

            page.on("request", on_request)
            try:
                page.goto(url, wait_until="load", timeout=30000)
                page.wait_for_timeout(SETTLE_MS)
            except Exception as exc:  # noqa: BLE001 - one dead seed must not stop the run
                print(f"skip {url}: {exc.__class__.__name__}", file=sys.stderr)
            ctx.close()
            hosts = sorted(seen.items(), key=lambda kv: kv[1])[:MAX_HOSTS]
            # Several seeds can share a host: keep the richest page load.
            if hosts and len(hosts) >= len(sites.get(page_host, [])):
                sites[page_host] = [[h, round(ms, -1)] for h, ms in hosts]
            print(f"{len(hosts):3d} hosts  {url}", file=sys.stderr)
        browser.close()
    return sites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=0, help="first N seeds only (testing)")
    args = ap.parse_args()
    with open(ROOT / "src/noisycompany/data/default.toml", "rb") as fh:
        ua = tomllib.load(fh)["http"]["user_agent"]
    urls = seed_urls()[: args.limit or None]
    data = {"generated": dt.date.today().strftime("%Y-%m"),
            "method": "headless Chromium, one load per persona seed, trackers removed",
            "sites": dict(sorted(snapshot(urls, ua).items()))}
    args.out.write_text(json.dumps(data, indent=1, sort_keys=False) + "\n", "utf-8")
    print(f"{len(data['sites'])} sites -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
