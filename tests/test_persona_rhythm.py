import datetime as dt
import random

import pytest

from noisycompany import config, packs, rhythm
from noisycompany.personas import PersonaRotator

SUN_9 = dt.datetime(2026, 3, 8, 9)
TUE_9 = dt.datetime(2026, 3, 3, 9)


def test_window_parsing_and_wrap():
    assert rhythm.persona_affinity(["sat-sun 07-12"], SUN_9) == rhythm.PEAK
    assert rhythm.persona_affinity(["sat-sun 07-12"], TUE_9) == rhythm.OFF_PEAK
    assert rhythm.persona_affinity(None, TUE_9) == 1.0
    night = ["fri 22-03"]
    assert rhythm.persona_affinity(night, dt.datetime(2026, 3, 6, 23)) == rhythm.PEAK
    assert rhythm.persona_affinity(night, dt.datetime(2026, 3, 7, 2)) == rhythm.PEAK  # Sat 2 am
    assert rhythm.persona_affinity(night, dt.datetime(2026, 3, 8, 2)) == rhythm.OFF_PEAK
    assert rhythm.in_window(rhythm.parse_window("sun-mon 10-11"), dt.datetime(2026, 3, 9, 10))
    for bad in ("weekend 7-12", "sat 25-26", "sat 07-07", "sat"):
        with pytest.raises(ValueError):
            rhythm.parse_window(bad)


def test_pick_follows_affinity():
    personas = {"gardening": {"rhythm": ["sat-sun 07-12"]}, "chess": {"rhythm": ["mon-sun 20-01"]}}
    rot = PersonaRotator(personas, 2, 10, salt="x")
    rng = random.Random(1)

    def share(now):
        aff = lambda p: rhythm.persona_affinity(p.get("rhythm"), now)  # noqa: E731
        picks = [rot.pick(rng, affinity=aff)[0] for _ in range(2000)]
        return picks.count("gardening") / len(picks)

    assert share(SUN_9) > 0.75
    assert share(dt.datetime(2026, 3, 3, 21)) < 0.3


def test_builtin_rhythms_are_valid():
    cfg = config.load()
    personas = config.load_personas(cfg)
    assert any("rhythm" in p for p in personas.values())
    data = {k: v for k, v in config.builtin_personas().items()}
    assert packs.validate(data, require_meta=False) == []
    data["gardening"] = dict(data["gardening"], rhythm=["someday 7-12"])
    assert any("rhythm" in e for e in packs.validate(data, require_meta=False))


def _burst_sizes(switches, seed=3):
    from collections import Counter

    from noisycompany import benchmark
    noise = benchmark.simulate_noise(switches, days=1, seed=seed)
    # Group third-party lookups by the second they start in.
    return Counter(int(e.ts) for e in noise if any(c in e.host for c in ("cdn.", "static.",
                                                                       "img.", "fonts.", "api.")))


def test_page_load_bursts_are_page_sized():
    small = _burst_sizes({"third_party_bursts": True})
    big = _burst_sizes({"page_load_bursts": True})
    assert max(small.values()) <= 4
    assert max(big.values()) >= 5


def test_interleave_skips_sessions_while_offline():
    from noisycompany import benchmark, study
    household = [study.Event(benchmark.START.timestamp() + 3600 * 20, "news.com")]
    quiet = benchmark.simulate_noise({"interleave_with_user": True}, 1, 2, household=household)
    plain = benchmark.simulate_noise({}, 1, 2, household=household)
    assert len(quiet) < len(plain)
