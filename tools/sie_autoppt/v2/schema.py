from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .layout_ids import SUPPORTED_LAYOUTS as LAYOUT_ID_SOURCE
from .style_variants import SUPPORTED_STYLE_VARIANTS
from .theme_loader import available_theme_names
from .utils import normalize_data_sources, normalize_string_list, strip_text

SUPPORTED_LAYOUTS = LAYOUT_ID_SOURCE
SUPPORTED_THEMES = tuple(available_theme_names())

class AutoPPTBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=False,
        extra="ignore",
    )


class TextStripMixin(AutoPPTBase):
    strip_required_fields: ClassVar[tuple[str, ...]] = ()
    strip_optional_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="before")
    @classmethod
    def _strip_declared_text_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in cls.strip_required_fields:
            if field_name in normalized:
                normalized[field_name] = strip_text(normalized.get(field_name))
        for field_name in cls.strip_optional_fields:
            if field_name in normalized:
                text = strip_text(normalized.get(field_name))
                normalized[field_name] = text or None
        return normalized


class ThemeMeta(AutoPPTBase):
    title: str = Field(min_length=1, max_length=80)
    theme: str = Field(default="sie_consulting_fixed")
    language: str = Field(default="zh-CN", min_length=2, max_length=16)
    author: str = Field(default="AI Auto PPT", min_length=1, max_length=40)
    version: str = Field(default="2.0", min_length=1, max_length=10)

    @field_validator("title", "theme", "language", "author", "version", mode="before")
    @classmethod
    def _strip_required_text(cls, value: Any) -> str:
        return strip_text(value)

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        if value not in SUPPORTED_THEMES:
            raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
        return value


class OutlineItem(TextStripMixin):
    strip_required_fields = ("title", "goal")
    page_no: int = Field(ge=1, le=20)
    title: str = Field(min_length=2, max_length=32)
    goal: str = Field(min_length=4, max_length=80)


class OutlineStrategy(AutoPPTBase):
    chapter_count: int = Field(ge=1, le=20)
    audience_tier: Literal["executive", "management", "practitioner", "mixed", "general"] = "general"
    narrative_pacing: Literal["fast", "balanced", "deep"] = "balanced"


class OutlineDocument(AutoPPTBase):
    pages: list[OutlineItem] = Field(min_length=1, max_length=20)
    story_rationale: str | None = Field(default=None, min_length=8, max_length=280)
    outline_strategy: OutlineStrategy | None = None

    @model_validator(mode="after")
    def _validate_page_numbers(self) -> "OutlineDocument":
        page_numbers = [item.page_no for item in self.pages]
        if page_numbers != list(range(1, len(page_numbers) + 1)):
            raise ValueError("outline page_no values must start at 1 and be contiguous.")
        return self

    def to_list(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self.pages]

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"pages": self.to_list()}
        if self.story_rationale:
            payload["story_rationale"] = self.story_rationale
        if self.outline_strategy is not None:
            payload["outline_strategy"] = self.outline_strategy.model_dump(mode="json")
        return payload


class ColumnBlock(TextStripMixin):
    strip_required_fields = ("heading",)
    heading: str = Field(min_length=1, max_length=24)
    items: list[str] = Field(min_length=1, max_length=6)

    @field_validator("items", mode="before")
    @classmethod
    def _normalize_items(cls, value: Any) -> list[str]:
        items = normalize_string_list(value)
        if not items:
            raise ValueError("items must contain at least one non-empty string.")
        return items


class ImageBlock(TextStripMixin):
    strip_optional_fields = ("caption", "path")
    mode: Literal["placeholder", "local_path"] = "placeholder"
    caption: str | None = Field(default=None, max_length=40)
    path: str | None = None

    @model_validator(mode="after")
    def _validate_path_requirement(self) -> "ImageBlock":
        if self.mode == "local_path" and not self.path:
            raise ValueError("path is required when image mode is local_path.")
        return self


class TimelineStage(TextStripMixin):
    strip_required_fields = ("title",)
    strip_optional_fields = ("detail",)
    title: str = Field(min_length=1, max_length=24)
    detail: str | None = Field(default=None, max_length=60)


class CardEntry(TextStripMixin):
    strip_required_fields = ("title",)
    strip_optional_fields = ("body",)
    title: str = Field(min_length=1, max_length=24)
    body: str | None = Field(default=None, max_length=60)


class MetricEntry(TextStripMixin):
    strip_required_fields = ("label", "value")
    strip_optional_fields = ("note",)
    label: str = Field(min_length=1, max_length=24)
    value: str = Field(min_length=1, max_length=24)
    note: str | None = Field(default=None, max_length=40)


class MatrixCell(TextStripMixin):
    strip_required_fields = ("title",)
    strip_optional_fields = ("body",)
    title: str = Field(min_length=1, max_length=24)
    body: str | None = Field(default=None, max_length=60)


class DataSourceNote(TextStripMixin):
    strip_required_fields = ("claim", "source")
    claim: str = Field(min_length=1, max_length=60)
    source: str = Field(min_length=1, max_length=80)
    confidence: Literal["high", "medium", "low"] = "medium"


class SlideAnnotations(TextStripMixin):
    strip_optional_fields: ClassVar[tuple[str, ...]] = ("anti_argument", "template_hint")
    anti_argument: str | None = Field(default=None, max_length=120)
    style_variant: Literal["minimal", "standard", "decorative"] | None = Field(default=None)
    template_hint: str | None = Field(default=None, max_length=80)
    data_sources: list[DataSourceNote] = Field(default_factory=list, max_length=4)

    @field_validator("style_variant", mode="before")
    @classmethod
    def _normalize_style_variant(cls, value: Any) -> str | None:
        text = strip_text(value)
        if not text:
            return None
        normalized = text.lower()
        if normalized not in SUPPORTED_STYLE_VARIANTS:
            raise ValueError(f"style_variant must be one of {', '.join(SUPPORTED_STYLE_VARIANTS)}")
        return normalized


class SectionBreakSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    strip_optional_fields = ("subtitle", "anti_argument")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["section_break"]
    title: str = Field(min_length=2, max_length=60)
    subtitle: str | None = Field(default=None, max_length=80)


class TitleOnlySlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_only"]
    title: str = Field(min_length=2, max_length=60)


class TitleContentSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_content"]
    title: str = Field(min_length=2, max_length=60)
    content: list[str] = Field(min_length=1, max_length=10)

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[str]:
        items = normalize_string_list(value)
        if not items:
            raise ValueError("content must contain at least one non-empty string.")
        return items


class TwoColumnsSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["two_columns"]
    title: str = Field(min_length=2, max_length=60)
    left: ColumnBlock
    right: ColumnBlock


class TitleImageSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["title_image"]
    title: str = Field(min_length=2, max_length=60)
    content: list[str] = Field(min_length=1, max_length=8)
    image: ImageBlock

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[str]:
        items = normalize_string_list(value)
        if not items:
            raise ValueError("content must contain at least one non-empty string.")
        return items


class TimelineSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    strip_optional_fields = ("heading", "anti_argument")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["timeline"]
    title: str = Field(min_length=2, max_length=60)
    heading: str | None = Field(default=None, max_length=40)
    stages: list[TimelineStage] = Field(min_length=2, max_length=6)


class StatsDashboardSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    strip_optional_fields = ("heading", "anti_argument")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["stats_dashboard"]
    title: str = Field(min_length=2, max_length=60)
    heading: str | None = Field(default=None, max_length=40)
    metrics: list[MetricEntry] = Field(min_length=2, max_length=6)
    insights: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("insights", mode="before")
    @classmethod
    def _normalize_insights(cls, value: Any) -> list[str]:
        return normalize_string_list(value)


class MatrixGridSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    strip_optional_fields = ("heading", "x_axis", "y_axis", "anti_argument")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["matrix_grid"]
    title: str = Field(min_length=2, max_length=60)
    heading: str | None = Field(default=None, max_length=40)
    x_axis: str | None = Field(default=None, max_length=24)
    y_axis: str | None = Field(default=None, max_length=24)
    cells: list[MatrixCell] = Field(min_length=2, max_length=4)


class CardsGridSlide(SlideAnnotations):
    strip_required_fields = ("slide_id", "title")
    strip_optional_fields = ("heading", "anti_argument")
    slide_id: str = Field(min_length=1, max_length=40)
    layout: Literal["cards_grid"]
    title: str = Field(min_length=2, max_length=60)
    heading: str | None = Field(default=None, max_length=40)
    cards: list[CardEntry] = Field(min_length=2, max_length=4)


SlideModel = Annotated[
    SectionBreakSlide
    | TitleOnlySlide
    | TitleContentSlide
    | TwoColumnsSlide
    | TitleImageSlide
    | TimelineSlide
    | StatsDashboardSlide
    | MatrixGridSlide
    | CardsGridSlide,
    Field(discriminator="layout"),
]


class DeckDocument(AutoPPTBase):
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
    default_theme: str = "sie_consulting_fixed",
    default_language: str = "zh-CN",
    default_author: str = "AI Auto PPT",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("deck payload must be a JSON object.")

    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    normalized_meta = {
        "title": strip_text(meta.get("title")) or default_title,
        "theme": strip_text(meta.get("theme")) or default_theme,
        "language": strip_text(meta.get("language")) or default_language,
        "author": strip_text(meta.get("author")) or default_author,
        "version": strip_text(meta.get("version")) or "2.0",
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
            slide["title"] = strip_text(slide["title"])
        if "layout" in slide:
            slide["layout"] = strip_text(slide["layout"])
        anti_argument = strip_text(slide.get("anti_argument"))
        if anti_argument:
            slide["anti_argument"] = anti_argument
        data_sources = normalize_data_sources(slide.get("data_sources"))
        if data_sources:
            slide["data_sources"] = data_sources
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
        if isinstance(slide, TimelineSlide):
            if len(slide.stages) > 5:
                warnings.append(f"[{slide.slide_id}] timeline has more than 5 stages and may become visually dense.")
        if isinstance(slide, StatsDashboardSlide):
            if len(slide.metrics) > 4:
                warnings.append(f"[{slide.slide_id}] stats_dashboard has more than 4 metrics and may need tighter spacing.")
        if isinstance(slide, MatrixGridSlide):
            if len(slide.cells) < 4:
                warnings.append(f"[{slide.slide_id}] matrix_grid uses fewer than 4 cells and may look sparse.")
        if isinstance(slide, CardsGridSlide):
            if len(slide.cards) > 3:
                warnings.append(f"[{slide.slide_id}] cards_grid has more than 3 cards and may require manual review.")
    return warnings


def validate_deck_payload(
    payload: dict[str, Any],
    *,
    default_title: str = "AI Auto PPT",
    default_theme: str = "sie_consulting_fixed",
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
