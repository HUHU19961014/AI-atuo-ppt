from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from ..schema import TitleOnlySlide
from ..theme_loader import ThemeSpec
from .common import add_blank_slide, add_card, add_page_number, add_textbox, fill_background


def render_title_only(prs, slide_data: TitleOnlySlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
    slide = add_blank_slide(prs)
    fill_background(slide, theme)
    add_card(slide, 0.95, 1.35, 11.45, 4.6, theme)
    add_textbox(
        slide,
        left=1.55,
        top=2.55,
        width=10.2,
        height=1.2,
        text=slide_data.title,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.title + 4,
        color_hex=theme.colors.primary,
        bold=True,
        align=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
