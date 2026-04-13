"""Legacy generator compatibility facade.

The default production path is V2 SVG-primary (`make` -> `v2-make`).
This module is intentionally lazy-loaded so importing CLI no longer imports
legacy implementation code on the primary path.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = (
    "build_output_path",
    "generate_ppt",
    "generate_ppt_artifacts_from_deck_plan",
    "generate_ppt_artifacts_from_deck_spec",
    "generate_ppt_artifacts_from_html",
    "validate_slide_pool_configuration",
)


def _legacy_module():
    return import_module("tools.sie_autoppt.legacy.generator")


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        return getattr(_legacy_module(), name)
    raise AttributeError(name)


__all__ = list(_EXPORTS)
