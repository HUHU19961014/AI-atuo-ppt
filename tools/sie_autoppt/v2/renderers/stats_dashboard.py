from __future__ import annotations

from ..schema import StatsDashboardSlide
from ..theme_loader import ThemeSpec
from .common import add_blank_slide, add_bullet_list, add_card, add_page_number, add_textbox, fill_background
from .layout_constants import STATS_DASHBOARD, TITLE_BAND


def _metric_grid(metrics_count: int) -> tuple[int, int]:
    if metrics_count <= 2:
        return 2, 1
    if metrics_count <= 4:
        return 2, 2
    return 3, 2


def render_stats_dashboard(prs, slide_data: StatsDashboardSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
    slide = add_blank_slide(prs)
    fill_background(slide, theme)
    add_textbox(
        slide,
        left=TITLE_BAND.left,
        top=TITLE_BAND.top,
        width=TITLE_BAND.width,
        height=TITLE_BAND.height,
        text=slide_data.title,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.title,
        color_hex=theme.colors.primary,
        bold=True,
    )

    if slide_data.heading:
        add_textbox(
            slide,
            left=TITLE_BAND.subtitle_left,
            top=STATS_DASHBOARD.heading_top,
            width=TITLE_BAND.subtitle_width,
            height=TITLE_BAND.subtitle_height,
            text=slide_data.heading,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.text_sub,
            bold=True,
        )

    metrics_top = STATS_DASHBOARD.metrics_top
    metrics_height = (
        STATS_DASHBOARD.metrics_height_with_insights
        if slide_data.insights
        else STATS_DASHBOARD.metrics_height_without_insights
    )
    metrics_width = STATS_DASHBOARD.metrics_width
    add_card(slide, STATS_DASHBOARD.metrics_card_left, metrics_top, metrics_width, metrics_height, theme)

    cols, rows = _metric_grid(len(slide_data.metrics))
    gap_x = STATS_DASHBOARD.metric_gap_x
    gap_y = STATS_DASHBOARD.metric_gap_y
    card_width = (metrics_width - STATS_DASHBOARD.metric_horizontal_inset - gap_x * (cols - 1)) / cols
    card_height = (metrics_height - STATS_DASHBOARD.metric_vertical_inset - gap_y * (rows - 1)) / rows

    for index, metric in enumerate(slide_data.metrics):
        row = index // cols
        col = index % cols
        left = STATS_DASHBOARD.metrics_card_left + STATS_DASHBOARD.metric_outer_left_padding + col * (card_width + gap_x)
        top = metrics_top + STATS_DASHBOARD.metric_outer_top_padding + row * (card_height + gap_y)
        add_card(slide, left, top, card_width, card_height, theme)
        add_textbox(
            slide,
            left=left + STATS_DASHBOARD.metric_label_left_padding,
            top=top + STATS_DASHBOARD.metric_label_top_padding,
            width=card_width - STATS_DASHBOARD.metric_label_left_padding * 2,
            height=STATS_DASHBOARD.metric_label_height,
            text=metric.label,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.text_sub,
            bold=True,
        )
        add_textbox(
            slide,
            left=left + STATS_DASHBOARD.metric_label_left_padding,
            top=top + STATS_DASHBOARD.metric_value_top_offset,
            width=card_width - STATS_DASHBOARD.metric_label_left_padding * 2,
            height=STATS_DASHBOARD.metric_value_height,
            text=metric.value,
            font_name=theme.fonts.title,
            font_size=theme.font_sizes.title + 2,
            color_hex=theme.colors.primary,
            bold=True,
        )
        if metric.note:
            add_textbox(
                slide,
                left=left + STATS_DASHBOARD.metric_label_left_padding,
                top=top + card_height - STATS_DASHBOARD.metric_note_bottom_padding,
                width=card_width - STATS_DASHBOARD.metric_label_left_padding * 2,
                height=STATS_DASHBOARD.metric_note_height,
                text=metric.note,
                font_name=theme.fonts.body,
                font_size=theme.font_sizes.small,
                color_hex=theme.colors.text_main,
            )

    if slide_data.insights:
        add_card(
            slide,
            STATS_DASHBOARD.insights_card.left,
            STATS_DASHBOARD.insights_card.top,
            STATS_DASHBOARD.insights_card.width,
            STATS_DASHBOARD.insights_card.height,
            theme,
        )
        add_textbox(
            slide,
            left=STATS_DASHBOARD.insights_title_left,
            top=STATS_DASHBOARD.insights_title_top,
            width=STATS_DASHBOARD.insights_title_width,
            height=STATS_DASHBOARD.insights_title_height,
            text="Key Insights",
            font_name=theme.fonts.title,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.secondary,
            bold=True,
        )
        add_bullet_list(
            slide,
            list(slide_data.insights),
            left=STATS_DASHBOARD.insights_body_left,
            top=STATS_DASHBOARD.insights_body_top,
            width=STATS_DASHBOARD.insights_body_width,
            height=STATS_DASHBOARD.insights_body_height,
            theme=theme,
            font_size=theme.font_sizes.small,
        )

    log.info(f"{slide_data.slide_id}: rendered semantic stats dashboard layout.")
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
