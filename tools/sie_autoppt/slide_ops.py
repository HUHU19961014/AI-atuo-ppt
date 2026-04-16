from __future__ import annotations

from .openxml_slide_ops import (
    copy_slide_xml_assets,
    import_slides_from_presentation,
    set_slide_metadata_names,
    slide_assets_preserved,
    slide_image_targets,
)
from .presentation_ops import clone_slide_after, ensure_last_slide, remove_slide

__all__ = [
    "clone_slide_after",
    "copy_slide_xml_assets",
    "ensure_last_slide",
    "import_slides_from_presentation",
    "remove_slide",
    "set_slide_metadata_names",
    "slide_assets_preserved",
    "slide_image_targets",
]
