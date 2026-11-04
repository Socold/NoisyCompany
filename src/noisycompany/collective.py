"""Collective noise (feature `collective_noise`).

Households that join the same collective share a random salt and a list of reviewed
personas. Their rotators then pick the **same decoy interests at the same time**, so an
observer comparing households cannot tell whose interests are real: the decoy profile is
common to all members (a k-anonymity of interests).

No server: a collective is a short share code (or file) passed by any channel (message,
QR code, paper). Safety rules, because a code comes from someone else:

- it can only reference personas already reviewed in this code base (built-in, locale,
  bundled packs). It cannot bring new domains, so a malicious member cannot steer your
  traffic (and IP address) to a server they control;
- the payload carries a SHA-256 digest; any alteration is rejected;
- the code is small, compressed JSON, never executed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import tomllib
import zlib
from importlib import resources
from pathlib import Path
from typing import Any

from noisycompany import packs
from noisycompany.config import ConfigError

PREFIX = "nc1:"
FORMAT = "noisycompany-collective"
MAX_CODE = 4096


def reviewed_personas() -> dict[str, dict[str, list[str]]]:
    """Every persona that went through review: built-in, locale packs, bundled packs."""
    out: dict[str, dict[str, list[str]]] = {}
    data = resources.files("noisycompany.data")
    for name in ("personas.toml", "personas_fr.toml"):
        out.update(tomllib.loads(data.joinpath(name).read_text("utf-8")))
    for pack in packs.bundled().values():
        out.update({k: v for k, v in pack.items() if k != "meta"})
    return out


def _digest(body: dict[str, Any]) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).hexdigest()


def create(name: str, personas: list[str], rotate_days: int = 10,
           active_count: int = 3) -> dict[str, Any]:
    body = {"format": FORMAT, "v": 1, "name": name, "salt": secrets.token_hex(16),
            "personas": sorted(set(personas)), "rotate_days": rotate_days,
            "active_count": active_count}
    validate(body)
    return body | {"digest": _digest(body)}


def validate(body: dict[str, Any]) -> None:
    if body.get("format") != FORMAT or body.get("v") != 1:
        raise ConfigError("not a NoisyCompany collective (format/version)")
    if not isinstance(body.get("name"), str) or not re.fullmatch(r"[\w .-]{1,40}", body["name"]):
        raise ConfigError("collective name: 1-40 letters, digits, space, . _ -")
    if not isinstance(body.get("salt"), str) or not re.fullmatch(r"[0-9a-f]{32}", body["salt"]):
        raise ConfigError("collective salt must be 32 hex characters")
    names = body.get("personas")
    if not isinstance(names, list) or not 2 <= len(names) <= 50:
        raise ConfigError("collective needs 2 to 50 personas")
    unknown = sorted(set(names) - set(reviewed_personas()))
    if unknown:
        raise ConfigError(f"collective references unreviewed personas: {unknown}")
    rd, ac = body.get("rotate_days"), body.get("active_count")
    if not isinstance(rd, int) or not 1 <= rd <= 60:
        raise ConfigError("rotate_days must be an integer in [1, 60]")
    if not isinstance(ac, int) or not 1 <= ac <= len(names):
        raise ConfigError("active_count must be in [1, number of personas]")


def encode(collective: dict[str, Any]) -> str:
    raw = json.dumps(collective, sort_keys=True, separators=(",", ":")).encode()
    return PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).rstrip(b"=").decode()


def decode(code: str) -> dict[str, Any]:
    code = code.strip()
    if not code.startswith(PREFIX) or len(code) > MAX_CODE:
        raise ConfigError("not a collective share code (expected nc1:...)")
    payload = code[len(PREFIX):]
    try:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)), 64_000)
        if not inflater.eof or inflater.unconsumed_tail or inflater.unused_data:
            raise ValueError("incomplete or oversized stream")  # truncated, or zip bomb
        data = json.loads(raw)
    except (ValueError, zlib.error) as exc:
        raise ConfigError("corrupted share code") from exc
    if not isinstance(data, dict):
        raise ConfigError("corrupted share code")
    digest = data.pop("digest", None)
    validate(data)
    if digest != _digest(data):
        raise ConfigError("share code digest mismatch: altered or truncated")
    return data | {"digest": digest}


def _path(state_dir: Path) -> Path:
    return state_dir / "collective.json"


def join(code: str, state_dir: Path) -> dict[str, Any]:
    collective = decode(code)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _path(state_dir)
    path.write_text(json.dumps(collective, indent=2))
    path.chmod(0o600)  # the salt is the shared secret of the collective
    return collective


def leave(state_dir: Path) -> bool:
    path = _path(state_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def current(state_dir: Path | None) -> dict[str, Any] | None:
    if not state_dir:
        return None
    try:
        data = json.loads(_path(state_dir).read_text())
        return decode(encode(data))  # re-validate what is on disk
    except (OSError, ValueError, ConfigError):
        return None
