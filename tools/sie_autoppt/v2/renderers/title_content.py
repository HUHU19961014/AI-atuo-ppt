from __future__ import annotations

from ..schema import TitleContentSlide
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


def render_title_content(prs, slide_data: TitleContentSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
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
    add_card(slide, 0.78, 1.28, 11.72, 4.95, theme)
    font_size = resolve_body_font_size(theme, len(slide_data.content))
    if len(slide_data.content) > 6:
        log.warn(f"{slide_data.slide_id}: content is dense, reduced bullet font size to {font_size}.")
    add_bullet_list(
        slide,
        slide_data.content,
        left=1.02,
        top=1.6,
        width=11.1,
        height=4.25,
        theme=theme,
        font_size=font_size,
    )
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
