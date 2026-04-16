from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from pptx.util import Inches

from ..schema import StatsDashboardSlide
from .common import RenderContext, add_blank_slide, add_bullet_list, add_card, add_page_number, add_textbox, fill_background
from .layout_dsl import Box, Grid
from .layout_constants import STATS_DASHBOARD, TITLE_BAND


def _metric_grid(metrics_count: int) -> tuple[int, int]:
    if metrics_count <= 2:
        return 2, 1
    if metrics_count <= 4:
        return 2, 2
    return 3, 2


def _insights_title(slide_data: StatsDashboardSlide) -> str:
    probe_text = "".join(
        [
            slide_data.title,
            slide_data.heading or "",
            *[metric.label + metric.value + (metric.note or "") for metric in slide_data.metrics],
            *slide_data.insights,
        ]
    )
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in probe_text)
    return "关键洞察" if has_cjk else "Key Insights"


def _to_numeric_metric(value: str) -> float | None:
    normalized = str(value or "").strip().replace(",", "")
    if not normalized:
        return None
    is_percent = normalized.endswith("%")
    if is_percent:
        normalized = normalized[:-1]
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _build_metrics_chart_image(slide_data: StatsDashboardSlide) -> Path | None:
    enabled = os.environ.get("SIE_AUTOPPT_STATS_CHART_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return None

    numeric_pairs: list[tuple[str, float]] = []
    for metric in slide_data.metrics:
        value = _to_numeric_metric(metric.value)
        if value is not None:
            numeric_pairs.append((metric.label, value))
    if len(numeric_pairs) < 2:
        return None

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    labels = [item[0] for item in numeric_pairs]
    values = [item[1] for item in numeric_pairs]
    temp_dir = Path(tempfile.mkdtemp(prefix="sie_stats_chart_"))
    chart_path = temp_dir / "stats_dashboard_chart.png"
    fig, ax = plt.subplots(figsize=(6.4, 2.2), dpi=150)
    ax.bar(labels, values)
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.set_title("Metric Snapshot", fontsize=10)
    fig.tight_layout()
    fig.savefig(chart_path, format="png", transparent=True)
    plt.close(fig)
    return chart_path


def render_stats_dashboard(
    ctx: RenderContext,
    slide_data: StatsDashboardSlide,
):
    prs = ctx.prs
    theme = ctx.theme
    log = ctx.log
    slide_number = ctx.slide_number
    total_slides = ctx.total_slides
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
    metrics_height = STATS_DASHBOARD.metrics_height_with_insights if slide_data.insights else STATS_DASHBOARD.metrics_height_without_insights
    metrics_width = STATS_DASHBOARD.metrics_width
    add_card(slide, STATS_DASHBOARD.metrics_card_left, metrics_top, metrics_width, metrics_height, theme)

    cols, rows = _metric_grid(len(slide_data.metrics))
    metrics_container = Box(
        left=STATS_DASHBOARD.metrics_card_left,
        top=metrics_top,
        width=metrics_width,
        height=metrics_height,
    ).inset(
        left=STATS_DASHBOARD.metric_outer_left_padding,
        top=STATS_DASHBOARD.metric_outer_top_padding,
        right=STATS_DASHBOARD.metric_horizontal_inset - STATS_DASHBOARD.metric_outer_left_padding,
        bottom=STATS_DASHBOARD.metric_vertical_inset - STATS_DASHBOARD.metric_outer_top_padding,
    )
    metric_cells = Grid(columns=cols, rows=rows, gap_x=STATS_DASHBOARD.metric_gap_x, gap_y=STATS_DASHBOARD.metric_gap_y).cells(metrics_container)

    for index, metric in enumerate(slide_data.metrics):
        cell = metric_cells[index]
        add_card(slide, cell.left, cell.top, cell.width, cell.height, theme)
        add_textbox(
            slide,
            left=cell.left + STATS_DASHBOARD.metric_label_left_padding,
            top=cell.top + STATS_DASHBOARD.metric_label_top_padding,
            width=cell.width - STATS_DASHBOARD.metric_label_left_padding * 2,
            height=STATS_DASHBOARD.metric_label_height,
            text=metric.label,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.text_sub,
            bold=True,
        )
        add_textbox(
            slide,
            left=cell.left + STATS_DASHBOARD.metric_label_left_padding,
            top=cell.top + STATS_DASHBOARD.metric_value_top_offset,
            width=cell.width - STATS_DASHBOARD.metric_label_left_padding * 2,
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
                left=cell.left + STATS_DASHBOARD.metric_label_left_padding,
                top=cell.top + cell.height - STATS_DASHBOARD.metric_note_bottom_padding,
                width=cell.width - STATS_DASHBOARD.metric_label_left_padding * 2,
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
            text=_insights_title(slide_data),
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
    else:
        chart_path = _build_metrics_chart_image(slide_data)
        if chart_path is not None and chart_path.exists():
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
                width=3.2,
                height=STATS_DASHBOARD.insights_title_height,
                text="Trend Snapshot",
                font_name=theme.fonts.title,
                font_size=theme.font_sizes.small + 1,
                color_hex=theme.colors.secondary,
                bold=True,
            )
            slide.shapes.add_picture(
                str(chart_path),
                Inches(STATS_DASHBOARD.chart_left),
                Inches(STATS_DASHBOARD.chart_top),
                Inches(STATS_DASHBOARD.chart_width),
                Inches(STATS_DASHBOARD.chart_height),
            )

    log.info(f"{slide_data.slide_id}: rendered semantic stats dashboard layout.")
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
