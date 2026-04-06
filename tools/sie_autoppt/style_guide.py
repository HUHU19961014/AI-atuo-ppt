from __future__ import annotations

from pathlib import Path
from typing import Any


def _coerce_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if "," in text:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if parts:
            return [_coerce_scalar(part) for part in parts]
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def _assign_nested(target: dict[str, Any], dotted_key: str, value: object) -> None:
    parts = [part.strip() for part in dotted_key.split(".") if part.strip()]
    if not parts:
        return
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def parse_style_guide_markdown(style_guide_path: Path) -> dict[str, Any]:
    text = style_guide_path.read_text(encoding="utf-8")
    data: dict[str, Any] = {
        "raw_text": text.strip(),
        "source_path": str(style_guide_path),
    }
    current_list_key = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        if line.startswith("#"):
            current_list_key = ""
            continue
        if line.startswith("- "):
            if current_list_key:
                existing = data.get(current_list_key, [])
                if not isinstance(existing, list):
                    existing = [existing]
                existing.append(line[2:].strip())
                data[current_list_key] = existing
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key:
            continue
        if normalized_value:
            _assign_nested(data, normalized_key, _coerce_scalar(normalized_value))
            current_list_key = ""
        else:
            data[normalized_key] = []
            current_list_key = normalized_key

    return data


def deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged
