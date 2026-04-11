from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator


def _strip_text(value: object) -> str:
    return str(value).strip()


class ThemePage(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ThemeColors(BaseModel):
    primary: str
    secondary: str
    text_main: str
    text_sub: str
    bg: str
    card_bg: str
    line: str

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_color(cls, value: object) -> str:
        text = _strip_text(value)
        if not text.startswith("#") or len(text) != 7:
            raise ValueError("theme color values must be in #RRGGBB format.")
        return text.upper()


class ThemeFonts(BaseModel):
    title: str
    body: str
    fallback: str

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_font(cls, value: object) -> str:
        return _strip_text(value)


class ThemeFontSizes(BaseModel):
    title: int = Field(ge=14, le=40)
    subtitle: int = Field(ge=10, le=24)
    body: int = Field(ge=10, le=24)
    small: int = Field(ge=8, le=18)


class ThemeSpacing(BaseModel):
    page_margin_left: float = Field(ge=0)
    page_margin_right: float = Field(ge=0)
    page_margin_top: float = Field(ge=0)
    page_margin_bottom: float = Field(ge=0)
    block_gap: float = Field(ge=0)


class ThemeSpec(BaseModel):
    theme_name: str
    page: ThemePage
    colors: ThemeColors
    fonts: ThemeFonts
    font_sizes: ThemeFontSizes
    spacing: ThemeSpacing

    @field_validator("theme_name", mode="before")
    @classmethod
    def _normalize_theme_name(cls, value: object) -> str:
        return _strip_text(value)


THEMES_DIR = Path(__file__).resolve().parent / "themes"


def available_theme_names() -> list[str]:
    if not THEMES_DIR.exists():
        raise FileNotFoundError(f"Theme directory does not exist: {THEMES_DIR}")
    theme_names = sorted(path.stem for path in THEMES_DIR.glob("*.json"))
    if not theme_names:
        raise FileNotFoundError(f"No theme JSON files found in {THEMES_DIR}")
    return theme_names


def load_theme(theme_name: str) -> ThemeSpec:
    theme_path = THEMES_DIR / f"{theme_name}.json"
    if not theme_path.exists():
        raise FileNotFoundError(
            f"Theme not found: {theme_name}. Available themes: {', '.join(available_theme_names())}"
        )
    data = json.loads(theme_path.read_text(encoding="utf-8"))
    try:
        return ThemeSpec.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Theme file is invalid: {theme_path}") from exc
