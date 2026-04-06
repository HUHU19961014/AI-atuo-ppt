from __future__ import annotations

from ..schema import TwoColumnsSlide
from ..theme_loader import ThemeSpec
from .common import (
    add_blank_slide,
    add_bullet_list,
    add_card,
    add_page_number,
    add_textbox,
    fill_background,
    resolve_body_font_size,
)


def render_two_columns(prs, slide_data: TwoColumnsSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
    slide = add_blank_slide(prs)
    fill_background(slide, theme)
    add_textbox(
        slide,
        left=0.78,
        top=0.5,
        width=11.7,
        height=0.55,
        text=slide_data.title,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.title,
        color_hex=theme.colors.primary,
        bold=True,
    )

    card_top = 1.32
    card_height = 4.9
    card_width = 5.55
    left_left = 0.78
    right_left = 7.05
    add_card(slide, left_left, card_top, card_width, card_height, theme)
    add_card(slide, right_left, card_top, card_width, card_height, theme)
    add_textbox(
        slide,
        left=left_left + 0.22,
        top=card_top + 0.18,
        width=card_width - 0.44,
        height=0.38,
        text=slide_data.left.heading,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.subtitle + 1,
        color_hex=theme.colors.secondary,
        bold=True,
    )
    add_textbox(
        slide,
        left=right_left + 0.22,
        top=card_top + 0.18,
        width=card_width - 0.44,
        height=0.38,
        text=slide_data.right.heading,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.subtitle + 1,
        color_hex=theme.colors.secondary,
        bold=True,
    )

    left_font_size = resolve_body_font_size(theme, len(slide_data.left.items))
    right_font_size = resolve_body_font_size(theme, len(slide_data.right.items))
    if len(slide_data.left.items) > 5 or len(slide_data.right.items) > 5:
        log.warn(f"{slide_data.slide_id}: two_columns content is dense and may need manual review.")
    add_bullet_list(
        slide,
        slide_data.left.items,
        left=left_left + 0.18,
        top=card_top + 0.62,
        width=card_width - 0.36,
        height=card_height - 0.86,
        theme=theme,
        font_size=left_font_size,
    )
    add_bullet_list(
        slide,
        slide_data.right.items,
        left=right_left + 0.18,
        top=card_top + 0.62,
        width=card_width - 0.36,
        height=card_height - 0.86,
        theme=theme,
        font_size=right_font_size,
    )
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
