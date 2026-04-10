from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT
from .exceptions import PromptRenderError, PromptTemplateError


PROMPTS_DIR = PROJECT_ROOT / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    path: Path
    body: str
    version: str
    placeholders: tuple[str, ...]


def _parse_prompt_metadata(raw_text: str) -> tuple[dict[str, str], str]:
    stripped = raw_text.lstrip()
    if not stripped.startswith("<!--"):
        return {}, raw_text.strip()

    start = raw_text.find("<!--")
    end = raw_text.find("-->", start + 4)
    if start != 0 or end == -1:
        return {}, raw_text.strip()

    metadata_block = raw_text[start + 4 : end].strip()
    body = raw_text[end + 3 :].strip()
    metadata: dict[str, str] = {}
    for line in metadata_block.splitlines():
        candidate = line.strip()
        if not candidate or ":" not in candidate:
            continue
        key, value = candidate.split(":", 1)
        metadata[key.strip().lower().replace("-", "_")] = value.strip()
    return metadata, body


def _extract_placeholders(template: str) -> tuple[str, ...]:
    placeholders: list[str] = []
    seen: set[str] = set()
    for _, field_name, _, _ in string.Formatter().parse(template):
        if not field_name:
            continue
        normalized = field_name.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        placeholders.append(normalized)
    return tuple(placeholders)


def _metadata_placeholders(metadata: dict[str, str], body: str) -> tuple[str, ...]:
    configured = metadata.get("required_placeholders", "").strip()
    if configured:
        return tuple(item.strip() for item in configured.split(",") if item.strip())
    return _extract_placeholders(body)


def resolve_prompt_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if not path.exists():
        raise PromptTemplateError(f"Prompt template not found: {relative_path}")
    return path


def load_prompt(relative_path: str) -> PromptTemplate:
    path = resolve_prompt_path(relative_path)
    raw_text = path.read_text(encoding="utf-8")
    metadata, body = _parse_prompt_metadata(raw_text)
    version = metadata.get("version", "").strip() or "0"
    return PromptTemplate(
        path=path,
        body=body,
        version=version,
        placeholders=_metadata_placeholders(metadata, body),
    )


def load_prompt_template(relative_path: str) -> str:
    return load_prompt(relative_path).body


def render_prompt_template(relative_path: str, **values: object) -> str:
    prompt = load_prompt(relative_path)
    missing = [key for key in prompt.placeholders if key not in values]
    if missing:
        raise PromptRenderError(
            f"Prompt template '{relative_path}' is missing required placeholders: {', '.join(missing)}"
        )
    rendered = prompt.body.format_map(values)
    unresolved = _extract_placeholders(rendered)
    if unresolved:
        raise PromptRenderError(
            f"Prompt template '{relative_path}' still contains unresolved placeholders after rendering: {', '.join(unresolved)}"
        )
    return rendered.strip()
