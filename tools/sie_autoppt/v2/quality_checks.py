from __future__ import annotations

from dataclasses import dataclass
import re

from .schema import DeckDocument, TitleContentSlide, TitleImageSlide, TwoColumnsSlide


WARNING_LEVEL_WARNING = "warning"
WARNING_LEVEL_HIGH = "high"
WARNING_LEVEL_ERROR = "error"


@dataclass(frozen=True)
class ContentWarning:
    slide_id: str
    warning_level: str
    message: str

    def to_log_line(self) -> str:
        return f"[{self.slide_id}] [{self.warning_level}] {self.message}"

    def is_error(self) -> bool:
        return self.warning_level == WARNING_LEVEL_ERROR


def _count_hanzi(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


# Directory-style keywords that indicate non-conclusive titles
DIRECTORY_KEYWORDS = {
    "背景", "问题", "方案", "架构", "路径", "现状", "分析", "介绍",
    "概述", "说明", "目标", "计划", "总结", "展望"
}


def _has_directory_style_title(title: str) -> bool:
    """Check if title contains directory-style keywords."""
    return any(keyword in title for keyword in DIRECTORY_KEYWORDS)


def _title_warnings(slide) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    hanzi_count = _count_hanzi(slide.title)

    # Error level: title too long (severe overflow risk)
    if hanzi_count > 28:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_ERROR,
                message=f"title contains {hanzi_count} Chinese characters, which exceeds the 28-character error threshold (severe overflow risk).",
            )
        )
    # High warning: title very long
    elif hanzi_count > 24:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_HIGH,
                message=f"title contains {hanzi_count} Chinese characters, which exceeds the 24-character high-warning threshold.",
            )
        )
    # Warning: title longer than recommended
    elif hanzi_count > 20:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title contains {hanzi_count} Chinese characters, which exceeds the 20-character recommended threshold.",
            )
        )

    # Warning: directory-style title (lacks conclusion orientation)
    if _has_directory_style_title(slide.title):
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title '{slide.title}' appears to be directory-style; consider making it more conclusion-oriented.",
            )
        )

    return warnings


def _title_content_warnings(slide: TitleContentSlide) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    bullet_count = len(slide.content)

    # Error level: bullet count severely out of range
    if bullet_count < 1 or bullet_count > 7:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_ERROR,
                message=f"title_content has {bullet_count} bullet items; must be between 1-7.",
            )
        )
    # Warning: bullet count outside recommended range
    elif bullet_count < 2 or bullet_count > 6:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title_content has {bullet_count} bullet items; recommended range is 2-6.",
            )
        )

    for index, item in enumerate(slide.content, start=1):
        item_length = len(item)
        # Error level: bullet extremely long (severe overflow risk)
        if item_length > 50:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_ERROR,
                    message=f"title_content bullet {index} length is {item_length}, which exceeds 50 characters (severe overflow risk).",
                )
            )
        # Warning: bullet longer than recommended
        elif item_length > 35:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_WARNING,
                    message=f"title_content bullet {index} length is {item_length}, which exceeds 35 characters (recommended threshold).",
                )
            )

    return warnings


def _two_columns_warnings(slide: TwoColumnsSlide) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    left_count = len(slide.left.items)
    right_count = len(slide.right.items)
    if left_count > 5:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"two_columns left column has {left_count} items, which exceeds 5.",
            )
        )
    if right_count > 5:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"two_columns right column has {right_count} items, which exceeds 5.",
            )
        )
    if abs(left_count - right_count) > 3:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"two_columns item count gap is {abs(left_count - right_count)}, which exceeds 3.",
            )
        )
    return warnings


def _title_image_warnings(slide: TitleImageSlide) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    content_count = len(slide.content)
    if content_count > 4:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title_image has {content_count} content items, which exceeds 4.",
            )
        )
    for index, item in enumerate(slide.content, start=1):
        item_length = len(item)
        # Error level: content extremely long
        if item_length > 50:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_ERROR,
                    message=f"title_image content {index} length is {item_length}, which exceeds 50 characters (severe overflow risk).",
                )
            )
        # Warning: content longer than recommended
        elif item_length > 35:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_WARNING,
                    message=f"title_image content {index} length is {item_length}, which exceeds 35 characters (recommended threshold).",
                )
            )
    return warnings


def check_slide_content(slide) -> list[ContentWarning]:
    warnings = _title_warnings(slide)
    if isinstance(slide, TitleContentSlide):
        warnings.extend(_title_content_warnings(slide))
    elif isinstance(slide, TwoColumnsSlide):
        warnings.extend(_two_columns_warnings(slide))
    elif isinstance(slide, TitleImageSlide):
        warnings.extend(_title_image_warnings(slide))
    return warnings


def check_deck_content(deck: DeckDocument) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    for slide in deck.slides:
        warnings.extend(check_slide_content(slide))
    warnings.extend(_check_deck_structure(deck))
    return warnings


def _check_deck_structure(deck: DeckDocument) -> list[ContentWarning]:
    """Check overall deck structure for best practices."""
    warnings: list[ContentWarning] = []

    if not deck.slides:
        return warnings

    first_slide = deck.slides[0]
    last_slide = deck.slides[-1]

    # Warning: first slide should ideally be section_break
    if first_slide.layout not in ("section_break", "title_only"):
        warnings.append(
            ContentWarning(
                slide_id=first_slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"first slide uses layout '{first_slide.layout}'; consider using 'section_break' to set context.",
            )
        )

    # Warning: last slide should ideally be title_only or section_break
    if last_slide.layout not in ("title_only", "section_break"):
        warnings.append(
            ContentWarning(
                slide_id=last_slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"last slide uses layout '{last_slide.layout}'; consider using 'title_only' to converge conclusion.",
            )
        )

    return warnings


def count_errors(warnings: list[ContentWarning]) -> int:
    """Count the number of error-level warnings."""
    return sum(1 for w in warnings if w.is_error())


def count_by_level(warnings: list[ContentWarning]) -> dict[str, int]:
    """Count warnings by level."""
    counts = {WARNING_LEVEL_ERROR: 0, WARNING_LEVEL_HIGH: 0, WARNING_LEVEL_WARNING: 0}
    for w in warnings:
        counts[w.warning_level] = counts.get(w.warning_level, 0) + 1
    return counts
