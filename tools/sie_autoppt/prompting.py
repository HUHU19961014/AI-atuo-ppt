from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT


PROMPTS_DIR = PROJECT_ROOT / "prompts"


class PromptTemplateError(FileNotFoundError):
    pass


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def resolve_prompt_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if not path.exists():
        raise PromptTemplateError(f"Prompt template not found: {relative_path}")
    return path


def load_prompt_template(relative_path: str) -> str:
    path = resolve_prompt_path(relative_path)
    return path.read_text(encoding="utf-8").strip()


def render_prompt_template(relative_path: str, **values: object) -> str:
    template = load_prompt_template(relative_path)
    return template.format_map(_SafeFormatDict(values)).strip()
