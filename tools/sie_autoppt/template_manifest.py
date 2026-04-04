import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .config import DEFAULT_TEMPLATE, DEFAULT_TEMPLATE_MANIFEST


@dataclass(frozen=True)
class ShapeBounds:
    min_top: int | None = None
    max_top: int | None = None
    min_width: int | None = None
    max_width: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "ShapeBounds":
        return cls(
            min_top=data.get("min_top"),
            max_top=data.get("max_top"),
            min_width=data.get("min_width"),
            max_width=data.get("max_width"),
        )

    def matches(self, shape) -> bool:
        top = getattr(shape, "top", None)
        width = getattr(shape, "width", None)
        if top is None or width is None:
            return False
        if self.min_top is not None and top <= self.min_top:
            return False
        if self.max_top is not None and top >= self.max_top:
            return False
        if self.min_width is not None and width <= self.min_width:
            return False
        if self.max_width is not None and width >= self.max_width:
            return False
        return True


@dataclass(frozen=True)
class TextBoxGeometry:
    left: int
    top: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "TextBoxGeometry":
        return cls(
            left=int(data["left"]),
            top=int(data["top"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )


@dataclass(frozen=True)
class SlideRoles:
    welcome: int
    theme: int
    directory: int
    body_template: int

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "SlideRoles":
        return cls(
            welcome=int(data["welcome"]),
            theme=int(data["theme"]),
            directory=int(data["directory"]),
            body_template=int(data["body_template"]),
        )


@dataclass(frozen=True)
class SlidePools:
    directory: tuple[int, ...] = ()
    body: tuple[int, ...] = ()
    ending: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SlidePools":
        return cls(
            directory=tuple(int(item) for item in data.get("directory", [])),
            body=tuple(int(item) for item in data.get("body", [])),
            ending=int(data["ending"]) if data.get("ending") is not None else None,
        )

    def supports(self, body_page_count: int, slide_count: int) -> bool:
        if self.ending is None:
            return False
        if len(self.directory) < body_page_count or len(self.body) < body_page_count:
            return False
        required_indices = list(self.directory[:body_page_count]) + list(self.body[:body_page_count]) + [self.ending]
        return max(required_indices, default=-1) < slide_count


@dataclass(frozen=True)
class TemplateSelectors:
    theme_title: ShapeBounds
    directory_title: ShapeBounds
    body_title: ShapeBounds
    body_subtitle: ShapeBounds
    body_render_area: ShapeBounds

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, int]]) -> "TemplateSelectors":
        return cls(
            theme_title=ShapeBounds.from_dict(data["theme_title"]),
            directory_title=ShapeBounds.from_dict(data["directory_title"]),
            body_title=ShapeBounds.from_dict(data["body_title"]),
            body_subtitle=ShapeBounds.from_dict(data["body_subtitle"]),
            body_render_area=ShapeBounds.from_dict(data["body_render_area"]),
        )


@dataclass(frozen=True)
class TemplateFallbackBoxes:
    body_title: TextBoxGeometry

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, int]]) -> "TemplateFallbackBoxes":
        return cls(
            body_title=TextBoxGeometry.from_dict(data["body_title"]),
        )


@dataclass(frozen=True)
class TemplateFonts:
    theme_title_pt: float
    directory_title_pt: float

    @classmethod
    def from_dict(cls, data: dict[str, int | float]) -> "TemplateFonts":
        return cls(
            theme_title_pt=float(data["theme_title_pt"]),
            directory_title_pt=float(data["directory_title_pt"]),
        )


@dataclass(frozen=True)
class TemplateManifest:
    manifest_path: str
    version: str
    template_name: str
    slide_roles: SlideRoles
    selectors: TemplateSelectors
    fallback_boxes: TemplateFallbackBoxes
    fonts: TemplateFonts
    slide_pools: SlidePools | None = None
    render_layouts: dict[str, dict[str, object]] = field(default_factory=dict)

    def render_layout(self, layout_id: str) -> dict[str, object]:
        layout = self.render_layouts.get(layout_id)
        if layout is None:
            raise KeyError(f"Render layout not found in manifest: {layout_id}")
        return layout

    def supports_preallocated_pool(self, body_page_count: int, slide_count: int) -> bool:
        return bool(self.slide_pools and self.slide_pools.supports(body_page_count, slide_count))


def resolve_template_manifest_path(template_path: Path | None = None) -> Path:
    selected_template = template_path or DEFAULT_TEMPLATE
    candidate = selected_template.with_suffix(".manifest.json")
    if candidate.exists():
        return candidate
    return DEFAULT_TEMPLATE_MANIFEST


@lru_cache(maxsize=None)
def _load_template_manifest_cached(manifest_path_str: str) -> TemplateManifest:
    manifest_path = Path(manifest_path_str)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return TemplateManifest(
        manifest_path=str(manifest_path),
        version=str(data["version"]),
        template_name=str(data["template_name"]),
        slide_roles=SlideRoles.from_dict(data["slide_roles"]),
        selectors=TemplateSelectors.from_dict(data["selectors"]),
        fallback_boxes=TemplateFallbackBoxes.from_dict(data["fallback_boxes"]),
        fonts=TemplateFonts.from_dict(data["fonts"]),
        slide_pools=SlidePools.from_dict(data["slide_pools"]) if data.get("slide_pools") else None,
        render_layouts=data.get("render_layouts", {}),
    )


def load_template_manifest(template_path: Path | None = None, manifest_path: Path | None = None) -> TemplateManifest:
    selected_manifest = manifest_path or resolve_template_manifest_path(template_path)
    if not selected_manifest.exists():
        raise FileNotFoundError(f"Template manifest not found: {selected_manifest}")
    return _load_template_manifest_cached(str(selected_manifest.resolve()))
