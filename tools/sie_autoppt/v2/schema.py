from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


SUPPORTED_THEMES = ("business_red", "tech_blue", "fresh_green")
SUPPORTED_LAYOUTS = (
    "section_break",
    "title_only",
    "title_content",
    "two_columns",
    "title_image",
)


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _strip_text(item)
        if text:
            normalized.append(text)
    return normalized


class ThemeMeta(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    theme: str = Field(default="business_red")
    language: str = Field(default="zh-CN", min_length=2, max_length=16)
    author: str = Field(default="AI Auto PPT", min_length=1, max_length=40)
    version: str = Field(default="2.0", min_length=1, max_length=10)

    @field_validator("title", "theme", "language", "author", "version", mode="before")
    @classmethod
    def _strip_required_text(cls, value: Any) -> str:
        return _strip_text(value)

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        if value not in SUPPORTED_THEMES:
            raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
        return value


class OutlineItem(BaseModel):
    page_no: int = Field(ge=1, le=20)
    title: str = Field(min_length=2, max_length=32)
    goal: str = Field(min_length=4, max_length=80)

    @field_validator("title", "goal", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _strip_text(value)


class OutlineDocument(BaseModel):
    pages: list[OutlineItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_page_numbers(self) -> "OutlineDocument":
        page_numbers = [item.page_no for item in self.pages]
        if page_numbers != list(range(1, len(page_numbers) + 1)):
            raise ValueError("outline page_no values must start at 1 and be contiguous.")
        return self

    def to_list(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self.pages]


class ColumnBlock(BaseModel):
    heading: str = Field(min_length=1, max_length=24)
    items: list[str] = Field(min_length=1, max_length=6)

    @field_validator("heading", mode="before")
    @classmethod
    def _strip_heading(cls, value: Any) -> str:
        return _strip_text(value)

    @field_validator("items", mode="before")
    @classmethod
    def _normalize_items(cls, value: Any) -> list[str]:
        items = _normalize_string_list(value)
        if not items:
            raise ValueError("items must contain at least one non-empty string.")
        return items


class ImageBlock(BaseModel):
    mode: Literal["placeholder", "local_path"] = "placeholder"
    caption: str | None = Field(default=None, max_length=40)
    path: str | None = None

    @field_validator("caption", "path", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: Any) -> str | None:
        text = _strip_text(value)
        return text or None

    @model_validator(mode="after")
    def _validate_path_requirement(self) -> "ImageBlock":
        if self.mode == "local_path" and not self.path:
            raise ValueError("path is required when image mode is local_path.")
        return self


class SectionBreakSlide(BaseModel):
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["section_break"]
    title: str = Field(min_length=2, max_length=60)
    subtitle: str | None = Field(default=None, max_length=80)

    @field_validator("slide_id", "title", "subtitle", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str | None:
        text = _strip_text(value)
        return text or None


class TitleOnlySlide(BaseModel):
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_only"]
    title: str = Field(min_length=2, max_length=60)

    @field_validator("slide_id", "title", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _strip_text(value)


class TitleContentSlide(BaseModel):
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_content"]
    title: str = Field(min_length=2, max_length=60)
    content: list[str] = Field(min_length=1, max_length=10)

    @field_validator("slide_id", "title", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _strip_text(value)

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[str]:
        items = _normalize_string_list(value)
        if not items:
            raise ValueError("content must contain at least one non-empty string.")
        return items


class TwoColumnsSlide(BaseModel):
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["two_columns"]
    title: str = Field(min_length=2, max_length=60)
    left: ColumnBlock
    right: ColumnBlock

    @field_validator("slide_id", "title", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _strip_text(value)


class TitleImageSlide(BaseModel):
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_image"]
    title: str = Field(min_length=2, max_length=60)
    content: list[str] = Field(min_length=1, max_length=8)
    image: ImageBlock

    @field_validator("slide_id", "title", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _strip_text(value)

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[str]:
        items = _normalize_string_list(value)
        if not items:
            raise ValueError("content must contain at least one non-empty string.")
        return items


SlideModel = Annotated[
    SectionBreakSlide | TitleOnlySlide | TitleContentSlide | TwoColumnsSlide | TitleImageSlide,
    Field(discriminator="layout"),
]


class DeckDocument(BaseModel):
    meta: ThemeMeta
    slides: list[SlideModel] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_slide_ids(self) -> "DeckDocument":
        seen: set[str] = set()
        for slide in self.slides:
            if slide.slide_id in seen:
                raise ValueError(f"duplicate slide_id detected: {slide.slide_id}")
            seen.add(slide.slide_id)
        return self


@dataclass(frozen=True)
class ValidatedDeck:
    deck: DeckDocument
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return self.deck.model_dump(mode="json")


def normalize_deck_payload(
    payload: dict[str, Any],
    *,
    default_title: str = "AI Auto PPT",
    default_theme: str = "business_red",
    default_language: str = "zh-CN",
    default_author: str = "AI Auto PPT",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("deck payload must be a JSON object.")

    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    normalized_meta = {
        "title": _strip_text(meta.get("title")) or default_title,
        "theme": _strip_text(meta.get("theme")) or default_theme,
        "language": _strip_text(meta.get("language")) or default_language,
        "author": _strip_text(meta.get("author")) or default_author,
        "version": _strip_text(meta.get("version")) or "2.0",
    }

    raw_slides = payload.get("slides", [])
    if not isinstance(raw_slides, list):
        raise ValueError("slides must be a list.")

    normalized_slides: list[dict[str, Any]] = []
    for index, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            raise ValueError(f"slide {index} must be an object.")
        slide = dict(raw_slide)
        slide.setdefault("slide_id", f"s{index}")
        if "title" in slide:
            slide["title"] = _strip_text(slide["title"])
        if "layout" in slide:
            slide["layout"] = _strip_text(slide["layout"])
        normalized_slides.append(slide)

    return {"meta": normalized_meta, "slides": normalized_slides}


def collect_deck_warnings(deck: DeckDocument) -> list[str]:
    warnings: list[str] = []
    for slide in deck.slides:
        if len(slide.title) > 24:
            warnings.append(f"[{slide.slide_id}] title is longer than 24 characters and may wrap to two lines.")
        if isinstance(slide, TitleContentSlide):
            if len(slide.content) > 6:
                warnings.append(f"[{slide.slide_id}] title_content has more than 6 bullet items.")
            for item in slide.content:
                if len(item) > 45:
                    warnings.append(f"[{slide.slide_id}] title_content bullet exceeds 45 characters.")
        if isinstance(slide, TwoColumnsSlide):
            if len(slide.left.items) > 5 or len(slide.right.items) > 5:
                warnings.append(f"[{slide.slide_id}] two_columns has a dense column that may need manual review.")
        if isinstance(slide, TitleImageSlide):
            if len(slide.content) > 5:
                warnings.append(f"[{slide.slide_id}] title_image has more than 5 bullet items.")
    return warnings


def validate_deck_payload(
    payload: dict[str, Any],
    *,
    default_title: str = "AI Auto PPT",
    default_theme: str = "business_red",
    default_language: str = "zh-CN",
    default_author: str = "AI Auto PPT",
) -> ValidatedDeck:
    normalized = normalize_deck_payload(
        payload,
        default_title=default_title,
        default_theme=default_theme,
        default_language=default_language,
        default_author=default_author,
    )
    try:
        deck = DeckDocument.model_validate(normalized)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return ValidatedDeck(deck=deck, warnings=tuple(collect_deck_warnings(deck)))
