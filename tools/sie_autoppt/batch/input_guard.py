from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class InputGuardConfig:
    max_bytes: int
    allowed_suffixes: set[str]


def validate_local_inputs(paths: list[Path], *, config: InputGuardConfig) -> list[Path]:
    validated: list[Path] = []
    for path in paths:
        if not path.exists():
            raise ValueError(f"input file does not exist: {path}")
        if path.suffix.lower() not in config.allowed_suffixes:
            raise ValueError(f"unsupported file suffix: {path.suffix}")
        if path.stat().st_size > config.max_bytes:
            raise ValueError(f"{path.name} exceeds size limit {config.max_bytes}")
        validated.append(path)
    return validated


_UNSAFE_TEXT_PATTERNS = (
    "ignore previous instructions",
    "reveal system prompt",
    "disregard all prior",
    "<script",
)
_URL_PATTERN = re.compile(r"https?://[^\s]+", flags=re.IGNORECASE)


def is_safe_text(text: str) -> bool:
    normalized = text.lower()
    return not any(pattern in normalized for pattern in _UNSAFE_TEXT_PATTERNS)


def validate_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid URL: {url}")
    return url


def validate_text_input(text: str, *, max_bytes: int = 2 * 1024 * 1024) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"text input exceeds size limit {max_bytes}")
    if not is_safe_text(text):
        raise ValueError("unsafe input text detected")
    for token in _URL_PATTERN.findall(text):
        validate_url(token)
    return text
