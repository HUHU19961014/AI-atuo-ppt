from __future__ import annotations

from typing import Callable

from pptx import Presentation

from ..plugins import plugin_layout_renderers
from .layout_ids import SUPPORTED_LAYOUTS
from .renderers.cards_grid import render_cards_grid
from .renderers.matrix_grid import render_matrix_grid
from .renderers.section_break import render_section_break
from .renderers.stats_dashboard import render_stats_dashboard
from .renderers.timeline import render_timeline
from .renderers.title_content import render_title_content
from .renderers.title_image import render_title_image
from .renderers.title_only import render_title_only
from .renderers.two_columns import render_two_columns
from .schema import SlideModel
from .theme_loader import ThemeSpec


LayoutRenderer = Callable[..., object]

LAYOUT_RENDERERS: dict[str, LayoutRenderer] = {
    "section_break": render_section_break,
    "title_only": render_title_only,
    "title_content": render_title_content,
    "two_columns": render_two_columns,
    "title_image": render_title_image,
    "timeline": render_timeline,
    "stats_dashboard": render_stats_dashboard,
    "matrix_grid": render_matrix_grid,
    "cards_grid": render_cards_grid,
}


def _validate_renderer_registry() -> None:
    supported = set(SUPPORTED_LAYOUTS)
    registered = set(LAYOUT_RENDERERS)
    missing = sorted(supported - registered)
    extra = sorted(registered - supported)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing renderers for: {', '.join(missing)}")
        if extra:
            details.append(f"unknown renderer layouts: {', '.join(extra)}")
        raise RuntimeError(f"V2 layout renderer registry mismatch ({'; '.join(details)}).")


_validate_renderer_registry()


def render_slide(
    prs: Presentation,
    slide_data: SlideModel,
    theme: ThemeSpec,
    log,
    slide_number: int,
    total_slides: int,
):
    layout = slide_data.layout
    active_renderers = {**LAYOUT_RENDERERS, **plugin_layout_renderers()}
    renderer = active_renderers.get(layout)
    if renderer is None:
        raise ValueError(f"Unsupported layout: {layout}")
    return renderer(prs, slide_data, theme, log, slide_number, total_slides)
