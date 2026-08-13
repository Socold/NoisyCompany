import json
import random
import threading

import pytest

from noisycompany import companion, config, impact, packs
from noisycompany.cli import main
from noisycompany.engine import Engine
from noisycompany.web import Fetcher, extract_assets


def engine(tmp_path):
    cfg = config.load()
    cfg["schedule"]["dwell_s"] = [0, 0]
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(5),
                 stop=threading.Event())
    eng._sleep = lambda s: True
    return eng


def test_business_profiles_are_valid_and_free_of_sensitive_topics():
    profiles = packs.business_profiles()
    assert {"office", "dev_team", "retail"} <= set(profiles)
    for name, data in profiles.items():
        assert packs.validate(data) == [], name


def test_business_profile_replaces_personas_and_is_labelled(tmp_path):
    eng = engine(tmp_path)
    eng.options["business_profile"] = "dev_team"
    eng.features.set("business_profiles", True)
    eng.features.set("labelled_log", True)
    eng.features.set("locale_packs", True)  # must not leak into a business profile
    eng.refresh_features()
    assert set(eng.rotator.personas) == {"dev_python", "dev_web"}
    for _ in range(15):
        eng.run_session()
    recs = [json.loads(x) for x in (tmp_path / "labelled.jsonl").read_text().splitlines()]
    assert recs and all(r["profile"] == "dev_team" for r in recs)
    assert all(r["persona"] in ("dev_python", "dev_web") for r in recs)
    eng.features.set("business_profiles", False)
    eng.refresh_features()
    assert "chess" in eng.rotator.personas


def test_unknown_business_profile_is_a_config_error():
    with pytest.raises(config.ConfigError):
        packs.business_personas("hospital")


HTML = """<html><head>
<link rel="stylesheet" href="/w/load.css?x=1"><link rel="icon" href="/favicon.ico">
<link rel="Stylesheet" href="https://cdn.other.org/a.css">
<script src="/w/startup.js"></script><script>inline()</script>
<script src="//en.wikipedia.org/w/two.js#frag"></script>
</head><body><a href="/wiki/X">x</a></body></html>"""


def test_extract_assets_same_origin_only():
    assets = extract_assets(HTML, "https://en.wikipedia.org/wiki/Chess")
    assert assets == ["https://en.wikipedia.org/w/load.css?x=1",
                      "https://en.wikipedia.org/w/startup.js",
                      "https://en.wikipedia.org/w/two.js"]


def test_subresources_behave_like_a_cache():
    f = Fetcher("UA", 5, 100_000, max_assets_per_page=2)
    first = f.subresources(HTML, "https://en.wikipedia.org/wiki/Chess")
    assert len(first) == 2
    second = f.subresources(HTML, "https://en.wikipedia.org/wiki/Rook")
    assert second == ["https://en.wikipedia.org/w/two.js"]
    assert f.subresources(HTML, "https://en.wikipedia.org/wiki/Pawn") == []


def test_request_trees_are_budgeted_and_labelled(tmp_path, monkeypatch):
    eng = engine(tmp_path)
    eng.features.set("request_trees", True)
    eng.features.set("labelled_log", True)
    monkeypatch.setattr(eng.fetcher, "fetch_asset", lambda url: 7000)
    monkeypatch.setattr(eng.fetcher, "allowed_by_robots", lambda url: (True, 0))
    before = eng.budget.bytes_today
    eng.fetch_tree(HTML, "https://en.wikipedia.org/wiki/Chess", "chess")
    assert eng.budget.bytes_today - before == 21000
    kinds = [json.loads(x)["kind"] for x in (tmp_path / "labelled.jsonl").read_text().splitlines()]
    assert kinds == ["subresource"] * 3


def test_estimate_accounts_for_request_trees():
    cfg = config.load(preset="eco")
    base = impact.estimate(cfg).mb_per_day_expected
    cfg["features"]["request_trees"] = True
    assert impact.estimate(cfg).mb_per_day_expected > base


def test_companion_files_are_generated_and_minimal(tmp_path):
    assert companion.export(tmp_path) == ["personas.js", "manifest.json"]
    assert companion.export(tmp_path, check=True) == []
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["manifest_version"] == 3
    assert all(h.startswith("https://") and h.endswith("/*") and "*." not in h
               for h in m["host_permissions"])
    assert "<all_urls>" not in json.dumps(m) and "tabs" not in m["permissions"]
    assert "chess" in (tmp_path / "personas.js").read_text()


def test_committed_companion_files_are_up_to_date():
    assert main(["companion", "export", "--check", "--dir", "companion/src"]) == 0


def test_request_trees_respect_robots(tmp_path, monkeypatch):
    eng = engine(tmp_path)
    fetched = []
    monkeypatch.setattr(eng.fetcher, "fetch_asset", lambda url: fetched.append(url) or 7000)
    monkeypatch.setattr(eng.fetcher, "allowed_by_robots",
                        lambda url: ("/w/" not in url, 0))
    eng.fetch_tree(HTML, "https://en.wikipedia.org/wiki/Chess", "chess")
    assert fetched == [] and eng.stats.robots_denied == 3
