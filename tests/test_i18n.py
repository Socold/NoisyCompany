import re
from pathlib import Path

from noisycompany import i18n

CLI = Path(__file__).parents[1] / "src/noisycompany/cli.py"


def test_language_detection():
    assert i18n.language({"LANG": "fr_FR.UTF-8"}) == "fr"
    assert i18n.language({"NOISYCOMPANY_LANG": "en", "LANG": "fr_FR.UTF-8"}) == "en"
    assert i18n.language({}) == "en"


def test_every_cli_message_is_translated_with_same_placeholders():
    ids = set(re.findall(r'_\("((?:[^"\\]|\\.)*)"', CLI.read_text()))
    assert ids and ids <= set(i18n.FR)
    for en, fr in i18n.FR.items():
        assert re.findall(r"\{[^}]*\}", en) == re.findall(r"\{[^}]*\}", fr), en


def test_cli_speaks_french(monkeypatch, capsys):
    from noisycompany import cli
    monkeypatch.setenv("NOISYCOMPANY_LANG", "fr")
    try:
        cli.main(["features", "on"])
    except SystemExit:
        pass
    assert "usage :" in capsys.readouterr().err
