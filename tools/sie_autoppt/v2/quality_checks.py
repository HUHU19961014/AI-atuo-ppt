from __future__ import annotations

from dataclasses import dataclass
import re

from .schema import DeckDocument, TitleContentSlide, TitleImageSlide, TwoColumnsSlide


WARNING_LEVEL_WARNING = "warning"
WARNING_LEVEL_HIGH = "high"


@dataclass(frozen=True)
class ContentWarning:
    slide_id: str
    warning_level: str
    message: str

    def to_log_line(self) -> str:
        return f"[{self.slide_id}] [{self.warning_level}] {self.message}"


def _count_hanzi(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _title_warnings(slide) -> list[ContentWarning]:
    hanzi_count = _count_hanzi(slide.title)
    if hanzi_count > 32:
        return [
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_HIGH,
                message=f"title contains {hanzi_count} Chinese characters, which exceeds the 32-character high-warning threshold.",
            )
        ]
    if hanzi_count > 24:
        return [
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title contains {hanzi_count} Chinese characters, which exceeds the 24-character warning threshold.",
            )
        ]
    return []


def _title_content_warnings(slide: TitleContentSlide) -> list[ContentWarning]:
    warnings: list[ContentWarning] = []
    bullet_count = len(slide.content)
    if bullet_count < 2 or bullet_count > 6:
        warnings.append(
            ContentWarning(
                slide_id=slide.slide_id,
                warning_level=WARNING_LEVEL_WARNING,
                message=f"title_content has {bullet_count} bullet items; recommended range is 2-6.",
            )
        )
    for index, item in enumerate(slide.content, start=1):
        if len(item) > 40:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_WARNING,
                    message=f"title_content bullet {index} length is {len(item)}, which exceeds 40 characters.",
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
        if len(item) > 40:
            warnings.append(
                ContentWarning(
                    slide_id=slide.slide_id,
                    warning_level=WARNING_LEVEL_WARNING,
                    message=f"title_image content {index} length is {len(item)}, which exceeds 40 characters.",
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
    return warnings
