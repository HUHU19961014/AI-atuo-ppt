from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from ..schema import SectionBreakSlide
from ..theme_loader import ThemeSpec
from .common import add_blank_slide, add_page_number, add_textbox, fill_background


def render_section_break(prs, slide_data: SectionBreakSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
    slide = add_blank_slide(prs)
    fill_background(slide, theme, theme.colors.primary)
    add_textbox(
        slide,
        left=0.9,
        top=1.55,
        width=11.3,
        height=1.15,
        text=slide_data.title,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.title + 6,
        color_hex="#FFFFFF",
        bold=True,
        align=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )
    if slide_data.subtitle:
        add_textbox(
            slide,
            left=1.4,
            top=2.9,
            width=10.5,
            height=0.55,
            text=slide_data.subtitle,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.subtitle + 1,
            color_hex="#F7EDEF",
            align=PP_ALIGN.CENTER,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
