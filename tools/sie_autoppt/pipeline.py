from __future__ import annotations

from importlib import import_module
from typing import Any

_LEGACY_MODULE = "tools.sie_autoppt.legacy.pipeline"
_EXPORTED = ("build_deck_plan", "plan_deck_from_html", "plan_deck_from_json")


def __getattr__(name: str) -> Any:
    if name not in _EXPORTED:
        raise AttributeError(name)
    module = import_module(_LEGACY_MODULE)
    return getattr(module, name)


__all__ = list(_EXPORTED)
