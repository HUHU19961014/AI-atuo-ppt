from __future__ import annotations

import importlib
import os
from threading import Lock
from typing import Any, Callable


LayoutRenderer = Callable[..., object]
ModelAdapterFactory = Callable[[str | None], Any]

_LAYOUT_RENDERERS: dict[str, LayoutRenderer] = {}
_MODEL_ADAPTERS: dict[str, ModelAdapterFactory] = {}
_LOADED_MODULES: set[str] = set()
_LOCK = Lock()


def register_layout_renderer(layout_name: str, renderer: LayoutRenderer) -> None:
    key = str(layout_name or "").strip()
    if not key:
        raise ValueError("layout_name must not be empty.")
    _LAYOUT_RENDERERS[key] = renderer


def register_model_adapter(name: str, factory: ModelAdapterFactory) -> None:
    key = str(name or "").strip().lower()
    if not key:
        raise ValueError("adapter name must not be empty.")
    _MODEL_ADAPTERS[key] = factory


def plugin_layout_renderers() -> dict[str, LayoutRenderer]:
    load_plugin_modules()
    return dict(_LAYOUT_RENDERERS)


def resolve_model_adapter(name: str) -> ModelAdapterFactory | None:
    load_plugin_modules()
    return _MODEL_ADAPTERS.get(str(name or "").strip().lower())


def load_plugin_modules() -> tuple[str, ...]:
    raw = os.environ.get("SIE_AUTOPPT_PLUGIN_MODULES", "").strip()
    if not raw:
        return ()
    module_names = tuple(part.strip() for part in raw.split(",") if part.strip())
    loaded_now: list[str] = []
    with _LOCK:
        for module_name in module_names:
            if module_name in _LOADED_MODULES:
                loaded_now.append(module_name)
                continue
            module = importlib.import_module(module_name)
            register_layout = getattr(module, "register_layout_renderers", None)
            if callable(register_layout):
                register_layout(register_layout_renderer)
            register_adapter = getattr(module, "register_model_adapters", None)
            if callable(register_adapter):
                register_adapter(register_model_adapter)
            _LOADED_MODULES.add(module_name)
            loaded_now.append(module_name)
    return tuple(loaded_now)


def reset_plugin_registry_for_tests() -> None:
    with _LOCK:
        _LAYOUT_RENDERERS.clear()
        _MODEL_ADAPTERS.clear()
        _LOADED_MODULES.clear()


__all__ = [
    "LayoutRenderer",
    "ModelAdapterFactory",
    "load_plugin_modules",
    "plugin_layout_renderers",
    "register_layout_renderer",
    "register_model_adapter",
    "resolve_model_adapter",
]
