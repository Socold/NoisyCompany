import json
import random
import threading

from noisycompany import config, packs, privacy
from noisycompany.cli import main
from noisycompany.engine import Engine


def firefox(home, prefs, addons=()):
    prof = home / ".mozilla/firefox/abc.default-release"
    prof.mkdir(parents=True)
    (prof / "prefs.js").write_text(
        "".join(f'user_pref("{k}", {json.dumps(v)});\n' for k, v in prefs.items()))
    (prof / "extensions.json").write_text(json.dumps(
        {"addons": [{"id": a, "active": True} for a in addons]}))
    return prof


def no_system(tmp_path):
    return {"resolved": lambda: "", "tempaddr_path": tmp_path / "missing"}


def by_id(report):
    return {c.id: c for c in report.checks}


def test_privacy_report_good_setup(tmp_path):
    firefox(tmp_path, {"network.trr.mode": 3, "browser.contentblocking.category": "strict",
                       "privacy.globalprivacycontrol.enabled": True},
            ["uBlock0@raymondhill.net"])
    tmp = tmp_path / "tempaddr"
    tmp.write_text("2\n")
    r = privacy.build_report(tmp_path, {"_running": True, "doh_sink": True},
                             resolved=lambda: "", tempaddr_path=tmp)
    c = by_id(r)
    assert c["blocker"].status == "pass" and "uBlock Origin" in c["blocker"].detail
    assert all(x.status == "pass" for x in r.checks if x.status != "unknown")
    assert r.score == 100


def test_privacy_report_flags_incoherent_dns_noise(tmp_path):
    firefox(tmp_path, {"network.trr.mode": 2})
    r = privacy.build_report(tmp_path, {"_running": True, "doh_sink": False}, **no_system(tmp_path))
    c = by_id(r)
    assert c["blocker"].status == "fail"
    assert c["noise_dns_coherence"].status == "fail"
    assert 0 < r.score < 100
    assert "Nothing was sent" in r.as_text()


def test_privacy_report_no_browser_is_unknown_not_fail(tmp_path):
    r = privacy.build_report(tmp_path, {}, **no_system(tmp_path))
    c = by_id(r)
    assert c["blocker"].status == "unknown" and c["encrypted_dns"].status == "unknown"


def test_privacy_report_never_leaks_paths(tmp_path):
    firefox(tmp_path, {"network.trr.mode": 3}, ["uBlock0@raymondhill.net"])
    text = json.dumps(privacy.build_report(tmp_path, {}, **no_system(tmp_path)).as_dict())
    assert str(tmp_path) not in text and "abc.default" not in text


def test_systemd_resolved_dot_detection():
    assert privacy.resolved_dot(lambda: "Protocols: +DefaultRoute -mDNS +DNSOverTLS")
    assert privacy.resolved_dot(lambda: "Protocols: -DNSOverTLS") is False


def test_chromium_doh_and_blocker(tmp_path):
    root = tmp_path / ".config/chromium"
    (root / "Default/Extensions/cjpalhdlnbpafiamejdnhcphjbkeiagm").mkdir(parents=True)
    (root / "Local State").write_text(json.dumps({"dns_over_https": {"mode": "secure"}}))
    c = by_id(privacy.build_report(tmp_path, {}, **no_system(tmp_path)))
    assert c["blocker"].status == "pass" and c["encrypted_dns"].status == "pass"


def test_bundled_packs_and_builtin_personas_are_valid():
    assert len(packs.bundled()) >= 4
    for name, data in packs.bundled().items():
        assert packs.validate(data) == [], name


def test_validator_rejects_sensitive_and_unsafe_packs():
    bad = {"meta": {"title": "x", "lang": "en", "description": "x", "version": 1},
           "casino_night": {"seeds": ["http://a.org/x", "https://evil.org/", "https://a.org/login"],
                            "domains": ["a.org"],
                            "queries": ["best poker", "online betting", "a", "b", "c"]}}
    errs = "\n".join(packs.validate(bad))
    assert "sensitive topic" in errs and "https URL" in errs
    assert "not in domains" in errs and "blocked fragment" in errs and "betting" in errs
    assert packs.validate({"meta": {}}) and packs.validate({})


def test_validator_has_no_false_positive_on_common_words():
    ok = {"meta": {"title": "Travel", "lang": "fr", "description": "x", "version": 1},
          "paris_walks": {"seeds": ["https://fr.wikipedia.org/wiki/Paris"] * 3,
                          "domains": ["fr.wikipedia.org"],
                          "queries": ["between two rivers", "essex coast", "armée de terre musée",
                                      "carcassonne", "betteraves"]}}
    assert packs.validate(ok) == []


def test_install_list_remove_and_engine_uses_pack(tmp_path, capsys):
    assert main(["packs", "install", "knitting", "--state-dir", str(tmp_path)]) == 0
    assert packs.installed(tmp_path) == ["knitting"]
    cfg = config.load()
    eng = Engine(cfg, config.load_personas(cfg), tmp_path, dry_run=True, rng=random.Random(0),
                 stop=threading.Event())
    eng.features.set("persona_marketplace", True)
    eng.refresh_features()
    assert "knitting" in eng.rotator.personas
    eng.features.set("persona_marketplace", False)
    eng.refresh_features()
    assert "knitting" not in eng.rotator.personas
    assert main(["packs", "remove", "knitting", "--state-dir", str(tmp_path)]) == 0
    assert packs.installed(tmp_path) == []


def test_tampered_installed_pack_is_ignored(tmp_path):
    packs.install("knitting", tmp_path)
    p = tmp_path / "packs/knitting.toml"
    p.write_text(p.read_text().replace("cable stitch", "online casino"))
    assert packs.installed_personas(tmp_path) == {}


def test_cli_packs_check_and_privacy(tmp_path, capsys):
    good = tmp_path / "good.toml"
    good.write_text(packs._bundled_dir().joinpath("photography.toml").read_text())
    assert main(["packs", "check", str(good)]) == 0
    bad = tmp_path / "bad.toml"
    bad.write_text("[meta]\ntitle='x'\n")
    assert main(["packs", "check", str(bad)]) == 1
    assert main(["privacy", "--json", "--state-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert '"score"' in out


def test_cli_packs_check_builtin_personas_without_meta():
    from importlib import resources
    base = resources.files("noisycompany.data")
    files = [str(base.joinpath(n)) for n in ("personas.toml", "personas_fr.toml")]
    assert main(["packs", "check", *files, "--no-meta"]) == 0
