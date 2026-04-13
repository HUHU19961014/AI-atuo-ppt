from __future__ import annotations

from typing import Any

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONDict = dict[str, JSONValue]

__all__ = ["JSONDict", "JSONScalar", "JSONValue"]
