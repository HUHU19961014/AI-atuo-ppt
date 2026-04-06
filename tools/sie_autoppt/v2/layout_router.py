from __future__ import annotations

from pptx import Presentation

from .renderers.section_break import render_section_break
from .renderers.title_content import render_title_content
from .renderers.title_image import render_title_image
from .renderers.title_only import render_title_only
from .renderers.two_columns import render_two_columns
from .schema import SlideModel
from .theme_loader import ThemeSpec


def render_slide(
    prs: Presentation,
    slide_data: SlideModel,
    theme: ThemeSpec,
    log,
    slide_number: int,
    total_slides: int,
):
    layout = slide_data.layout
    if layout == "section_break":
        return render_section_break(prs, slide_data, theme, log, slide_number, total_slides)
    if layout == "title_only":
        return render_title_only(prs, slide_data, theme, log, slide_number, total_slides)
    if layout == "title_content":
        return render_title_content(prs, slide_data, theme, log, slide_number, total_slides)
    if layout == "two_columns":
        return render_two_columns(prs, slide_data, theme, log, slide_number, total_slides)
    if layout == "title_image":
        return render_title_image(prs, slide_data, theme, log, slide_number, total_slides)
    raise ValueError(f"Unsupported layout: {layout}")
