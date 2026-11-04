"""Separability study (feature `separability_study`): how easily can an observer filter
the noise out?

Inputs, both local:
- the labelled log written by NoisyCompany (`labelled_log` switch), i.e. the noise;
- a trace of real activity on the same network, exported by the user: CSV or JSONL with
  a timestamp and a hostname per line (a Pi-hole / AdGuard Home / dnsmasq query log export
  works), Pi-hole's `pihole-FTL.db` directly, or AdGuard Home's `querylog.json`.

Method: both streams are cut into time windows; each window becomes a feature vector of
what a network observer sees (volume, host diversity, revisits, timing, hour of day). A
logistic regression (pure Python) is trained with k-fold cross-validation and scored by
ROC AUC: 0.5 = noise indistinguishable, 1.0 = trivially filtered. The weights tell which
features give the noise away, so personas and pacing can be improved.

Honest limit: this is one observer model among many (no TLS fingerprint, no payload
sizes). A high AUC is a real warning; a low AUC is not a proof of safety.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import random
import sqlite3
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from noisycompany import rhythm

FEATURES = [
    "events", "unique_hosts", "unique_ratio", "gap_mean", "gap_std", "gap_max",
    "revisit_ratio", "label_depth", "www_ratio", "hour_sin", "hour_cos", "day_off",
]


@dataclass(frozen=True)
class Event:
    ts: float
    host: str


def _parse_ts(value: str) -> float:
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _host(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if "://" in value:
        value = value.split("://", 1)[1].split("/", 1)[0]
    return value.split(":")[0]


def load_noise(path: Path) -> list[Event]:
    out = []
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        out.append(Event(_parse_ts(str(rec["ts"])), _host(rec["target"])))
    return sorted(out, key=lambda e: e.ts)


TS_KEYS = ("ts", "timestamp", "time", "date", "t")  # t / qh: AdGuard Home querylog
HOST_KEYS = ("host", "domain", "name", "query", "target", "qh")
FTL_DAYS_MAX = 400


def load_pihole_db(path: Path) -> list[Event]:
    """Pi-hole FTL database (read-only): every query's timestamp and domain."""
    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        # `queries` is a view over query_storage + domain_by_id in FTL v5.
        cur = db.execute("SELECT timestamp, domain FROM queries WHERE timestamp > "
                         "strftime('%s','now') - ? ORDER BY timestamp",
                         (FTL_DAYS_MAX * 86400,))
        return [Event(float(ts), _host(str(d))) for ts, d in cur if d]


def load_trace(path: Path) -> list[Event]:
    """CSV (header with a time and a domain column), JSONL with the same keys, or a
    Pi-hole FTL database."""
    with path.open("rb") as fh:
        if fh.read(16) == b"SQLite format 3\x00":
            return load_pihole_db(path)
    text = path.read_text("utf-8", errors="replace")
    rows: Iterable[dict[str, str]]
    if text.lstrip().startswith("{"):
        rows = (json.loads(x) for x in text.splitlines() if x.strip())
    else:
        rows = csv.DictReader(text.splitlines())
    out = []
    for row in rows:
        low = {str(k).strip().lower(): str(v) for k, v in row.items() if k is not None}
        ts = next((low[k] for k in TS_KEYS if low.get(k)), None)
        host = next((low[k] for k in HOST_KEYS if low.get(k)), None)
        if ts is None or host is None:
            continue
        try:
            out.append(Event(_parse_ts(ts), _host(host)))
        except ValueError:
            continue
    return sorted(out, key=lambda e: e.ts)


def windows(events: list[Event], width_s: float) -> list[list[Event]]:
    out: list[list[Event]] = []
    current: list[Event] = []
    start = None
    for e in events:
        if start is None or e.ts >= start + width_s:
            if current:
                out.append(current)
            current, start = [], e.ts - (e.ts % width_s)
        current.append(e)
    if current:
        out.append(current)
    return out


def featurize(stream: list[list[Event]]) -> list[list[float]]:
    seen: set[str] = set()
    rows = []
    for w in stream:
        hosts = [e.host for e in w]
        uniq = set(hosts)
        gaps = [b.ts - a.ts for a, b in zip(w, w[1:], strict=False)] or [0.0]
        revisit = len(uniq & seen) / len(uniq)
        seen |= uniq
        start = dt.datetime.fromtimestamp(w[0].ts)
        hour = start.hour + start.minute / 60
        rows.append([
            math.log1p(len(w)), math.log1p(len(uniq)), len(uniq) / len(w),
            math.log1p(statistics.fmean(gaps)), math.log1p(statistics.pstdev(gaps)),
            math.log1p(max(gaps)), revisit,
            statistics.fmean(h.count(".") for h in uniq),
            sum(h.startswith("www.") for h in uniq) / len(uniq),
            math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24),
            float(rhythm.day_off(start.date())),
        ])
    return rows


def _standardize(train: list[list[float]], test: list[list[float]]):
    cols = list(zip(*train, strict=True))
    mu = [statistics.fmean(c) for c in cols]
    sd = [statistics.pstdev(c) or 1.0 for c in cols]

    def z(rows):
        return [[(x - m) / s for x, m, s in zip(r, mu, sd, strict=True)] for r in rows]
    return z(train), z(test)


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x > -60 else 0.0


def fit(x: list[list[float]], y: list[int], epochs: int = 300, lr: float = 0.3,
        l2: float = 0.01) -> tuple[list[float], float]:
    n, d = len(x), len(x[0])
    w, b = [0.0] * d, 0.0
    for _ in range(epochs):
        gw, gb = [0.0] * d, 0.0
        for xi, yi in zip(x, y, strict=True):
            err = _sigmoid(sum(a * c for a, c in zip(w, xi, strict=True)) + b) - yi
            for j in range(d):
                gw[j] += err * xi[j]
            gb += err
        w = [wj - lr * (g / n + l2 * wj) for wj, g in zip(w, gw, strict=True)]
        b -= lr * gb / n
    return w, b


def auc(scores: list[float], labels: list[int]) -> float:
    """ROC AUC by the rank (Mann-Whitney) formula, ties averaged."""
    pairs = sorted(zip(scores, labels, strict=True))
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    pos = sum(lab for _, lab in pairs)
    neg = len(pairs) - pos
    if not pos or not neg:
        return float("nan")
    rank_sum = sum(r for r, (_, lab) in zip(ranks, pairs, strict=True) if lab)
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


@dataclass
class StudyResult:
    auc: float
    folds: int
    noise_windows: int
    human_windows: int
    weights: dict[str, float]

    def verdict(self) -> str:
        if self.auc != self.auc:
            return "not enough data"
        if self.auc >= 0.9:
            return "noise is trivially separable by this observer model"
        if self.auc >= 0.75:
            return "noise is largely separable"
        if self.auc >= 0.6:
            return "noise is partly separable"
        return "noise is hard to separate with these features"

    def as_text(self) -> str:
        top = sorted(self.weights.items(), key=lambda kv: -abs(kv[1]))[:5]
        lines = [
            f"Windows: {self.noise_windows} noise, {self.human_windows} real "
            f"({self.folds}-fold CV)",
            f"ROC AUC: {self.auc:.3f}  -> {self.verdict()}",
            "Most telling features (weight > 0 = looks like noise):",
            *[f"  {name:14} {wt:+.2f}" for name, wt in top],
            "AUC 0.5 = indistinguishable, 1.0 = trivially filtered. One observer model only.",
        ]
        return "\n".join(lines)


def run(noise: list[Event], human: list[Event], window_s: float = 600, folds: int = 5,
        seed: int = 0) -> StudyResult:
    xn = featurize(windows(noise, window_s))
    xh = featurize(windows(human, window_s))
    return cross_validate(xn, xh, FEATURES, folds, seed)


def cross_validate(xn: list[list[float]], xh: list[list[float]], names: list[str],
                   folds: int = 5, seed: int = 0) -> StudyResult:
    """k-fold logistic regression, noise = 1. Shared by the DNS and the pcap studies."""
    data = [(x, 1) for x in xn] + [(x, 0) for x in xh]
    if len(xn) < folds or len(xh) < folds:
        return StudyResult(float("nan"), folds, len(xn), len(xh), {})
    random.Random(seed).shuffle(data)
    scores, labels = [], []
    for k in range(folds):
        test = data[k::folds]
        train = [d for i, d in enumerate(data) if i % folds != k]
        xtr, xte = _standardize([d[0] for d in train], [d[0] for d in test])
        w, b = fit(xtr, [d[1] for d in train])
        scores += [sum(a * c for a, c in zip(w, x, strict=True)) + b for x in xte]
        labels += [d[1] for d in test]
    xall, _ = _standardize([d[0] for d in data], [])
    w, _ = fit(xall, [d[1] for d in data])
    return StudyResult(auc(scores, labels), folds, len(xn), len(xh),
                       dict(zip(names, w, strict=True)))
