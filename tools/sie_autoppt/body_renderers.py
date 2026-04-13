"""Legacy body renderer compatibility facade.

Primary generation no longer imports this module by default.
Use only for legacy compatibility paths.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = (
    "PATTERN_RENDERERS",
    "_layout_for_page",
    "apply_theme_title",
    "choose_font_size_by_length",
    "choose_title_font_size",
    "fill_body_slide",
    "fill_directory_slide",
    "pick_text_shapes",
    "resolve_render_pattern",
    "split_title_detail",
)


def _legacy_module():
    return import_module("tools.sie_autoppt.legacy.body_renderers")


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        return getattr(_legacy_module(), name)
    raise AttributeError(name)


__all__ = list(_EXPORTS)
