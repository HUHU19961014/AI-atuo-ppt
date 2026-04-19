from __future__ import annotations

import hashlib
from pathlib import Path


def _format_digest(raw: bytes) -> str:
    return f"sha256:{raw.hex()}"


def sha256_bytes(payload: bytes) -> str:
    return _format_digest(hashlib.sha256(payload).digest())


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())
