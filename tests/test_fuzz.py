"""Seeded mutation fuzzing of every parser that reads untrusted input.

Runs in a second in CI (fixed seed, a few thousand cases). Set NC_FUZZ_CASES to run
longer locally; `fuzz/atheris_targets.py` drives the same targets with coverage-guided
fuzzing when atheris is installed.
"""

import os
import random

import pytest

from noisycompany import collective
from noisycompany.config import ConfigError
from noisycompany.web import MAX_DECODED_BYTES, _decode, extract_assets, extract_links

CASES = int(os.environ.get("NC_FUZZ_CASES", "1500"))
SEED_HTML = (b'<html><head><link rel="stylesheet" href="/s.css"><script src="a.js"></script>'
             b'</head><body><a href="/wiki/X">x</a><a href="https://e.org/?q=1#f">y</a>'
             b"<a href='javascript:alert(1)'>z</a></body></html>")
TOKENS = [b"<a href=", b"<", b">", b'"', b"'", b"&#", b"<!--", b"]]>", b"\x00", b"\xff",
          b"http://[::1", b"//", b"\\", b"%00", b"<script src=", b"\n"]


def mutate(rng: random.Random, data: bytes) -> bytes:
    buf = bytearray(data)
    for _ in range(rng.randint(1, 8)):
        op = rng.random()
        pos = rng.randrange(len(buf) + 1)
        if op < 0.4:
            buf[pos:pos] = rng.choice(TOKENS)
        elif op < 0.7 and buf:
            del buf[pos:pos + rng.randint(1, 16)]
        elif buf:
            buf[min(pos, len(buf) - 1)] = rng.randrange(256)
    return bytes(buf)


def test_link_parsers_never_raise():
    rng = random.Random(1)
    for _ in range(CASES):
        html = mutate(rng, SEED_HTML).decode("utf-8", "replace")
        for url in extract_links(html, "https://en.wikipedia.org/wiki/A"):
            assert url.split(":", 1)[0] in ("http", "https")
        extract_assets(html, "https://en.wikipedia.org/wiki/A")


@pytest.mark.parametrize("encoding", ["gzip", "deflate", ""])
def test_decoder_never_raises_and_stays_capped(encoding):
    import gzip
    import zlib
    rng = random.Random(2)
    seed = {"gzip": gzip.compress(SEED_HTML * 50), "deflate": zlib.compress(SEED_HTML * 50),
            "": SEED_HTML}[encoding]
    for _ in range(CASES // 3):
        out = _decode(mutate(rng, seed), encoding, rng.choice(["utf-8", "latin-1", "nope"]))
        assert len(out) <= MAX_DECODED_BYTES


def test_share_code_decoder_only_raises_config_error():
    rng = random.Random(3)
    good = collective.encode(collective.create("Fuzz", ["chess", "gardening"], 10, 2))
    for _ in range(CASES):
        code = mutate(rng, good.encode()).decode("ascii", "replace")
        try:
            collective.decode(code)
        except ConfigError:
            pass
