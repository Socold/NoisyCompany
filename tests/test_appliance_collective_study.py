import json
import random
import threading

import pytest

from noisycompany import collective, config, study
from noisycompany.cli import main
from noisycompany.config import ConfigError
from noisycompany.engine import Engine
from noisycompany.personas import PersonaRotator


def engine(tmp_path):
    cfg = config.load()
    cfg["schedule"]["dwell_s"] = [0, 0]
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(2),
                 stop=threading.Event())
    eng._sleep = lambda s: True
    return eng


# ---------------------------------------------------------------- appliance / health
def test_health_command(tmp_path):
    args = ["health", "--state-dir", str(tmp_path)]
    assert main(args) == 0  # switch off: always healthy (Docker HEALTHCHECK safe)
    assert main(["features", "on", "appliance_packages", "--state-dir", str(tmp_path)]) == 0
    assert main(args) == 1  # no heartbeat yet
    eng = engine(tmp_path)
    eng.heartbeat()
    assert main(args) == 0
    assert main([*args, "--max-age", "-1"]) == 1


def test_heartbeat_only_when_switched_on(tmp_path):
    eng = engine(tmp_path)
    eng.heartbeat()
    assert not (tmp_path / "health").exists()


def test_long_sleep_keeps_heartbeat(tmp_path):
    eng = engine(tmp_path)
    eng.features.set("appliance_packages", True)
    beats = []
    eng.heartbeat = lambda: beats.append(1)
    del eng._sleep  # use the real one, with a fake stop event that never waits
    eng.stop = type("S", (), {"wait": lambda self, t: False})()
    assert eng._sleep(250)
    assert len(beats) == 4


def test_ha_addon_entrypoint_writes_valid_config(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ha_run", "deploy/homeassistant/run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    opts = {"preset": "eco", "daily_mb": 2.5, "active_hours": ["08:00-22:00"],
            "locale_packs": True, "doh_sink": False, "privacy_report": True}
    (tmp_path / "options.json").write_text(json.dumps(opts))
    monkeypatch.setattr(mod, "OPTIONS", str(tmp_path / "options.json"))
    (tmp_path / "salt").write_text("legacy")  # state of an add-on <= 2.0.1
    state = tmp_path / "state"
    monkeypatch.setattr(mod, "DATA", str(tmp_path))
    monkeypatch.setattr(mod, "STATE", str(state))
    monkeypatch.setattr(mod, "CONFIG", str(state / "nc.toml"))
    calls = []
    monkeypatch.setattr(mod.os, "execvp", lambda *a: calls.append(a))
    mod.main()
    cfg = config.load(state / "nc.toml")
    assert cfg["budget"]["daily_mb"] == 2.5 and cfg["features"]["appliance_packages"]
    assert calls and calls[0][1][:2] == ["noisycompany", "run"]
    assert calls[0][1][-1] == str(state) and (state / "salt").read_text() == "legacy"


# ---------------------------------------------------------------- collective
def test_collective_roundtrip_and_shared_rotation(tmp_path):
    group = collective.create("Famille", ["chess", "jazz", "hiking", "cooking"], 7, 2)
    code = collective.encode(group)
    assert code.startswith("nc1:") and len(code) < 600
    a, b = tmp_path / "a", tmp_path / "b"
    collective.join(code, a)
    collective.join(code, b)
    assert (a / "collective.json").stat().st_mode & 0o077 == 0
    engines = []
    for d in (a, b):
        eng = engine(d)
        eng.features.set("collective_noise", True)
        eng.refresh_features()
        engines.append(eng)
    assert engines[0].active_personas() == engines[1].active_personas()
    assert set(engines[0].rotator.personas) == {"chess", "jazz", "hiking", "cooking"}
    # households outside the collective (own salt) diverge at some point
    own = [PersonaRotator(engines[0].rotator.personas, 2, 7, tmp_path / f"o{i}").active()
           for i in range(8)]
    assert any(o != engines[0].active_personas() for o in own)


def test_collective_rejects_tampering_and_unreviewed_domains():
    good = collective.create("x", ["chess", "jazz"], active_count=2)
    code = collective.encode(good)
    evil = dict(good, personas=["chess", "my_tracking_server"])
    with pytest.raises(ConfigError, match="unreviewed"):
        collective.validate({k: v for k, v in evil.items() if k != "digest"})
    forged = collective.encode(dict(good, rotate_days=1))  # digest no longer matches
    with pytest.raises(ConfigError, match="digest"):
        collective.decode(forged)
    with pytest.raises(ConfigError):
        collective.decode(code[:-6])
    with pytest.raises(ConfigError):
        collective.decode("nc1:" + "A" * 5000)


def test_collective_cli(tmp_path, capsys):
    s = str(tmp_path)
    assert main(["collective", "create", "--name", "Voisins", "--personas", "chess,jazz,hiking",
                 "--state-dir", s]) == 0
    code = capsys.readouterr().out.strip()
    assert main(["collective", "join", code, "--state-dir", s]) == 0
    share = tmp_path / "code.txt"
    share.write_text(code + "\n")
    assert main(["collective", "join", str(share), "--state-dir", s]) == 0
    assert main(["collective", "--state-dir", s]) == 0
    assert "Voisins" in capsys.readouterr().out
    assert main(["collective", "leave", "--state-dir", s]) == 0
    assert collective.current(tmp_path) is None


# ---------------------------------------------------------------- study
def synth(kind, n_windows, rng, start=1_780_000_000):
    out = []
    for w in range(n_windows):
        t0 = start + w * 600
        if kind == "noise":   # sparse, few hosts, slow
            for i in range(rng.randint(1, 3)):
                out.append(study.Event(t0 + i * rng.uniform(30, 90), "en.wikipedia.org"))
        else:                 # bursts of many third-party hosts
            for i in range(rng.randint(15, 60)):
                out.append(study.Event(t0 + i * rng.uniform(0.05, 3),
                                       f"cdn{rng.randint(0, 40)}.example{rng.randint(0, 9)}.com"))
    return out


def test_auc_basics():
    assert study.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert study.auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0
    assert study.auc([0.5] * 4, [0, 1, 0, 1]) == 0.5


def test_study_detects_separable_and_inseparable_streams():
    rng = random.Random(1)
    sep = study.run(synth("noise", 40, rng), synth("human", 40, rng, start=1_780_100_000))
    assert sep.auc > 0.9 and "trivially" in sep.verdict()
    # Same behaviour over the same hours (hour of day is itself a telling feature).
    same = study.run(synth("noise", 40, rng), synth("noise", 40, rng, start=1_780_000_300))
    assert same.auc < 0.75


def test_study_cli_with_pihole_like_csv(tmp_path):
    rng = random.Random(3)
    noise = tmp_path / "labelled.jsonl"
    noise.write_text("\n".join(json.dumps({"ts": e.ts, "target": "https://" + e.host + "/x"})
                               for e in synth("noise", 30, rng)))
    trace = tmp_path / "queries.csv"
    rows = ["timestamp,type,domain,client"] + [
        f"{e.ts},A,{e.host},192.0.2.10" for e in synth("human", 30, rng, start=1_780_200_000)]
    trace.write_text("\n".join(rows))
    assert main(["study", "--noise", str(noise), "--human", str(trace), "--json"]) == 0


def test_collective_expiry_rotation_and_qr(tmp_path, capsys):
    import datetime as dt

    from noisycompany import qr
    from noisycompany.config import ConfigError
    group = collective.create("Famille", ["chess", "jazz", "hiking"], 7, 2,
                              expires=dt.date(2026, 1, 31))
    assert collective.expired(group, dt.date(2026, 2, 1))
    assert not collective.expired(group, dt.date(2026, 1, 31))
    with pytest.raises(ConfigError):  # already expired today
        collective.join(collective.encode(group), tmp_path)
    fresh = collective.create("Famille", ["chess", "jazz", "hiking"], 7, 2)
    collective.join(collective.encode(fresh), tmp_path)
    assert main(["collective", "rotate", "--state-dir", str(tmp_path),
                 "--expires-days", "30", "--svg", str(tmp_path / "c.svg")]) == 0
    rotated = collective.current(tmp_path)
    assert rotated["salt"] != fresh["salt"] and rotated["personas"] == fresh["personas"]
    assert rotated["expires"] and (tmp_path / "c.svg").read_text().startswith("<svg")
    code = capsys.readouterr().out.strip()
    assert qr.encode(code).version <= 15
    bad = dict(fresh, extra="x")
    bad.pop("digest")
    with pytest.raises(ConfigError):
        collective.validate(bad)
