from __future__ import annotations

from .common import add_blank_slide, add_card, add_page_number, add_textbox, fill_background, rgb
from .layout_constants import MATRIX_GRID, TITLE_BAND
from ..schema import MatrixGridSlide
from ..theme_loader import ThemeSpec


def render_matrix_grid(prs, slide_data: MatrixGridSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
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
            top=MATRIX_GRID.heading_top,
            width=TITLE_BAND.subtitle_width,
            height=TITLE_BAND.subtitle_height,
            text=slide_data.heading,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.text_sub,
            bold=True,
        )

    if slide_data.x_axis:
        add_textbox(
            slide,
            left=MATRIX_GRID.x_axis_left,
            top=MATRIX_GRID.x_axis_top,
            width=MATRIX_GRID.x_axis_width,
            height=MATRIX_GRID.x_axis_height,
            text=slide_data.x_axis,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small,
            color_hex=theme.colors.text_sub,
            bold=True,
        )
    if slide_data.y_axis:
        add_textbox(
            slide,
            left=MATRIX_GRID.y_axis_left,
            top=MATRIX_GRID.y_axis_top,
            width=MATRIX_GRID.y_axis_width,
            height=MATRIX_GRID.y_axis_height,
            text=slide_data.y_axis,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small,
            color_hex=theme.colors.text_sub,
            bold=True,
        )

    add_card(
        slide,
        MATRIX_GRID.outer_card.left,
        MATRIX_GRID.outer_card.top,
        MATRIX_GRID.outer_card.width,
        MATRIX_GRID.outer_card.height,
        theme,
    )

    for index, cell in enumerate(slide_data.cells[:4]):
        left, top = MATRIX_GRID.cell_positions[index]
        shape = add_card(slide, left, top, MATRIX_GRID.cell_width, MATRIX_GRID.cell_height, theme)
        shape.fill.fore_color.rgb = rgb(MATRIX_GRID.palette[index % len(MATRIX_GRID.palette)])
        add_textbox(
            slide,
            left=left + MATRIX_GRID.card_title_left_padding,
            top=top + MATRIX_GRID.card_title_top_padding,
            width=MATRIX_GRID.card_title_width,
            height=MATRIX_GRID.card_title_height,
            text=cell.title,
            font_name=theme.fonts.title,
            font_size=theme.font_sizes.subtitle,
            color_hex=theme.colors.secondary,
            bold=True,
        )
        if cell.body:
            add_textbox(
                slide,
                left=left + MATRIX_GRID.card_title_left_padding,
                top=top + MATRIX_GRID.card_body_top_offset,
                width=MATRIX_GRID.card_body_width,
                height=MATRIX_GRID.card_body_height,
                text=cell.body,
                font_name=theme.fonts.body,
                font_size=theme.font_sizes.small + 1,
                color_hex=theme.colors.text_main,
            )

    log.info(f"{slide_data.slide_id}: rendered semantic matrix grid layout.")
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
