"""Coverage-guided fuzzing (optional): pip install atheris; python fuzz/atheris_targets.py <target>.

Targets: links, decode, share_code. The seeded tests in tests/test_fuzz.py run in CI.
"""

import sys

import atheris

with atheris.instrument_imports():
    from noisycompany import collective
    from noisycompany.config import ConfigError
    from noisycompany.web import _decode, extract_links


def links(data: bytes) -> None:
    extract_links(data.decode("utf-8", "replace"), "https://en.wikipedia.org/wiki/A")


def decode(data: bytes) -> None:
    _decode(data, "gzip", "utf-8")


def share_code(data: bytes) -> None:
    try:
        collective.decode("nc1:" + data.decode("ascii", "replace"))
    except ConfigError:
        pass


if __name__ == "__main__":
    target = {"links": links, "decode": decode, "share_code": share_code}[sys.argv.pop(1)]
    atheris.Setup(sys.argv, target)
    atheris.Fuzz()
