from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from ..theme_loader import ThemeSpec

# All geometry values in this module use inches for 16:9 slides (13.33 x 7.5 in).

@dataclass(frozen=True)
class TitleBandLayout:
    left: float = 0.78
    top: float = 0.5
    width: float = 11.7
    height: float = 0.55
    subtitle_left: float = 0.82
    subtitle_width: float = 11.5
    subtitle_height: float = 0.28


@dataclass(frozen=True)
class FullCardLayout:
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True)
class TwoColumnLayout:
    card_top: float = 1.32
    card_height: float = 4.9
    card_width: float = 5.55
    left_left: float = 0.78
    right_left: float = 7.05
    inner_horizontal_padding: float = 0.18
    inner_card_text_padding: float = 0.22
    heading_top_offset: float = 0.18
    heading_height: float = 0.38
    bullet_top_offset: float = 0.62
    bullet_bottom_padding: float = 0.86
    table_left: float = 0.78
    table_top: float = 1.32
    table_width: float = 11.82
    table_height: float = 4.9


@dataclass(frozen=True)
class DynamicTwoColumnLayout:
    card_top: float
    card_height: float
    left_left: float
    right_left: float
    left_card_width: float
    right_card_width: float
    spacing: float
    font_size: float


@dataclass(frozen=True)
class TitleContentLayout:
    card: FullCardLayout = FullCardLayout(left=0.78, top=1.28, width=11.72, height=4.95)
    timeline_left: float = 1.0
    timeline_top: float = 1.55
    timeline_width: float = 11.06
    timeline_height: float = 4.2
    content_left: float = 1.02
    content_top: float = 1.6
    content_width: float = 11.1
    content_height: float = 4.25


@dataclass(frozen=True)
class CardsGridLayout:
    heading_left: float = 0.82
    heading_top: float = 1.04
    heading_width: float = 11.5
    heading_height: float = 0.28
    card_title_left_padding: float = 0.14
    card_title_top_padding: float = 0.16
    card_title_height: float = 0.34
    card_body_top_offset: float = 0.6
    card_body_bottom_padding: float = 0.78


@dataclass(frozen=True)
class TitleOnlyLayout:
    card: FullCardLayout = FullCardLayout(left=0.95, top=1.35, width=11.45, height=4.6)
    title_left: float = 1.55
    title_top: float = 2.55
    title_width: float = 10.2
    title_height: float = 1.2


@dataclass(frozen=True)
class TitleImageLayout:
    left_card: FullCardLayout = FullCardLayout(left=0.78, top=1.32, width=5.2, height=4.85)
    right_card: FullCardLayout = FullCardLayout(left=6.2, top=1.32, width=6.3, height=4.85)
    content_left: float = 1.0
    content_top: float = 1.65
    content_width: float = 4.75
    content_height: float = 4.1
    visual_left: float = 6.45
    visual_top: float = 1.58
    visual_width: float = 5.8
    visual_height: float = 4.33


@dataclass(frozen=True)
class TimelineLayout:
    subtitle_top: float = 1.08
    card: FullCardLayout = FullCardLayout(left=0.78, top=1.42, width=11.72, height=4.8)
    flow_left: float = 1.0
    flow_top: float = 1.7
    flow_width: float = 11.1
    flow_height: float = 4.1


@dataclass(frozen=True)
class MatrixGridLayout:
    heading_top: float = 1.05
    outer_card: FullCardLayout = FullCardLayout(left=1.55, top=1.42, width=10.95, height=4.65)
    cell_positions: tuple[tuple[float, float], ...] = ((1.78, 1.68), (7.08, 1.68), (1.78, 4.01), (7.08, 4.01))
    cell_width: float = 5.14
    cell_height: float = 2.17
    card_title_left_padding: float = 0.14
    card_title_top_padding: float = 0.14
    card_title_width: float = 4.86
    card_title_height: float = 0.3
    card_body_top_offset: float = 0.56
    card_body_width: float = 4.86
    card_body_height: float = 1.24
    x_axis_left: float = 5.3
    x_axis_top: float = 6.03
    x_axis_width: float = 2.6
    x_axis_height: float = 0.2
    y_axis_left: float = 0.84
    y_axis_top: float = 3.35
    y_axis_width: float = 0.9
    y_axis_height: float = 0.35
    palette_roles: tuple[str, ...] = ("card_bg", "bg", "card_bg", "bg")


@dataclass(frozen=True)
class StatsDashboardLayout:
    heading_top: float = 1.06
    metrics_card_left: float = 0.78
    metrics_top: float = 1.42
    metrics_width: float = 11.72
    metrics_height_without_insights: float = 4.65
    metrics_height_with_insights: float = 3.6
    metric_outer_left_padding: float = 0.18
    metric_outer_top_padding: float = 0.18
    metric_horizontal_inset: float = 0.36
    metric_vertical_inset: float = 0.34
    metric_gap_x: float = 0.16
    metric_gap_y: float = 0.16
    metric_label_left_padding: float = 0.12
    metric_label_top_padding: float = 0.14
    metric_label_height: float = 0.28
    metric_value_top_offset: float = 0.48
    metric_value_height: float = 0.54
    metric_note_bottom_padding: float = 0.62
    metric_note_height: float = 0.4
    insights_card: FullCardLayout = FullCardLayout(left=0.78, top=5.22, width=11.72, height=1.0)
    insights_title_left: float = 1.0
    insights_title_top: float = 5.35
    insights_title_width: float = 2.0
    insights_title_height: float = 0.24
    insights_body_left: float = 2.6
    insights_body_top: float = 5.3
    insights_body_width: float = 9.45
    insights_body_height: float = 0.62
    chart_left: float = 1.9
    chart_top: float = 5.42
    chart_width: float = 9.9
    chart_height: float = 0.68


@dataclass(frozen=True)
class SectionBreakLayout:
    title_left: float = 0.9
    title_top: float = 1.55
    title_width: float = 11.3
    title_height: float = 1.15
    subtitle_left: float = 1.4
    subtitle_top: float = 2.9
    subtitle_width: float = 10.5
    subtitle_height: float = 0.55


TITLE_BAND = TitleBandLayout()
TWO_COLUMNS = TwoColumnLayout()
TITLE_CONTENT = TitleContentLayout()
CARDS_GRID = CardsGridLayout()
TITLE_ONLY = TitleOnlyLayout()
TITLE_IMAGE = TitleImageLayout()
TIMELINE = TimelineLayout()
MATRIX_GRID = MatrixGridLayout()
STATS_DASHBOARD = StatsDashboardLayout()
SECTION_BREAK = SectionBreakLayout()


@lru_cache(maxsize=8)
def cards_grid_positions(card_count: int) -> tuple[tuple[float, float, float, float], ...]:
    if card_count == 2:
        return (
            (0.9, 1.5, TWO_COLUMNS.card_width, 4.55),
            (6.05, 1.5, TWO_COLUMNS.card_width, 4.55),
        )
    if card_count == 3:
        return ((0.85, 1.64, 3.72, 4.2), (4.79, 1.64, 3.72, 4.2), (8.73, 1.64, 3.72, 4.2))
    return ((0.9, 1.52, 5.5, 2.1), (6.0, 1.52, 5.5, 2.1), (0.9, 3.92, 5.5, 2.1), (6.0, 3.92, 5.5, 2.1))


def resolve_matrix_grid_layout(theme: ThemeSpec) -> MatrixGridLayout:
    override = theme.layouts.matrix_outer_card
    if override is None:
        return MATRIX_GRID
    return replace(
        MATRIX_GRID,
        outer_card=FullCardLayout(
            left=override.left,
            top=override.top,
            width=override.width,
            height=override.height,
        ),
    )


def calculate_two_column_layout(
    *,
    left_items_count: int,
    right_items_count: int,
    density_factor: float = 0.5,
) -> DynamicTwoColumnLayout:
    card_top = TWO_COLUMNS.card_top
    card_height = TWO_COLUMNS.card_height
    left_left = TWO_COLUMNS.left_left
    base_gap = max(0.28, min(0.52, 0.52 - max(0.0, min(1.0, density_factor)) * 0.24))
    total_width = 13.33 - left_left - 0.78

    left_count = max(0, int(left_items_count))
    right_count = max(0, int(right_items_count))
    if left_count == 0 and right_count == 0:
        left_ratio = 0.5
    elif left_count == 0:
        left_ratio = 0.0
    elif right_count == 0:
        left_ratio = 1.0
    else:
        left_ratio = left_count / (left_count + right_count)

    left_card_width = max(0.0, round((total_width - base_gap) * left_ratio, 3))
    right_card_width = max(0.0, round((total_width - base_gap) - left_card_width, 3))

    # Ensure both columns remain readable when both sides carry content.
    min_column_width = 3.25
    if left_count > 0 and right_count > 0:
        if left_card_width < min_column_width:
            shift = min_column_width - left_card_width
            left_card_width += shift
            right_card_width = max(min_column_width, right_card_width - shift)
        elif right_card_width < min_column_width:
            shift = min_column_width - right_card_width
            right_card_width += shift
            left_card_width = max(min_column_width, left_card_width - shift)

    right_left = left_left + left_card_width + base_gap
    max_items = max(left_count, right_count, 1)
    font_size = max(10.0, 14.0 - max(0, max_items - 4) * 0.5)

    return DynamicTwoColumnLayout(
        card_top=card_top,
        card_height=card_height,
        left_left=left_left,
        right_left=right_left,
        left_card_width=left_card_width,
        right_card_width=right_card_width,
        spacing=base_gap,
        font_size=font_size,
    )
