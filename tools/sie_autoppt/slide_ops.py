from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTED = (
    "clone_slide_after",
    "copy_slide_xml_assets",
    "ensure_last_slide",
    "import_slides_from_presentation",
    "remove_slide",
    "set_slide_metadata_names",
    "slide_assets_preserved",
    "slide_image_targets",
)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTED:
        raise AttributeError(name)
    if name in {"clone_slide_after", "ensure_last_slide", "remove_slide"}:
        module = import_module("tools.sie_autoppt.legacy.presentation_ops")
    else:
        module = import_module("tools.sie_autoppt.legacy.openxml_slide_ops")
    return getattr(module, name)


__all__ = list(_EXPORTED)
