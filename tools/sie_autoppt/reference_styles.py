from __future__ import annotations

from importlib import import_module
from typing import Any

_LEGACY_MODULE = "tools.sie_autoppt.legacy.reference_styles"
_EXPORTED = (
    "REFERENCE_STYLE_LIBRARY",
    "build_reference_import_plan",
    "fill_reference_style_slide",
    "get_reference_slide_no",
    "locate_reference_slide_no",
    "populate_reference_body_pages",
)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTED:
        raise AttributeError(name)
    module = import_module(_LEGACY_MODULE)
    return getattr(module, name)


__all__ = [
    "REFERENCE_STYLE_LIBRARY",
    "build_reference_import_plan",
    "fill_reference_style_slide",
    "get_reference_slide_no",
    "locate_reference_slide_no",
    "populate_reference_body_pages",
]
