from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_LAYOUT_TYPES = ("sales_proof", "risk_to_value", "executive_summary")
SUPPORTED_COMPONENT_TYPES = (
    "headline",
    "subheadline",
    "hero_claim",
    "proof_card",
    "risk_card",
    "value_band",
    "footer_note",
)


@dataclass(frozen=True)
class VisualSafeArea:
    left: int = 72
    top: int = 92
    right: int = 72
    bottom: int = 54

    def __post_init__(self) -> None:
        for name in ("left", "top", "right", "bottom"):
            if getattr(self, name) < 0:
                raise ValueError(f"safe_area.{name} must be >= 0")

    def to_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualSafeArea":
        return cls(
            left=int(data.get("left", 72)),
            top=int(data.get("top", 92)),
            right=int(data.get("right", 72)),
            bottom=int(data.get("bottom", 54)),
        )


@dataclass(frozen=True)
class VisualCanvas:
    width: int = 1280
    height: int = 720
    safe_area: VisualSafeArea = field(default_factory=VisualSafeArea)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("canvas width/height must be positive")
        if self.safe_area.left + self.safe_area.right >= self.width:
            raise ValueError("safe area left+right must be smaller than width")
        if self.safe_area.top + self.safe_area.bottom >= self.height:
            raise ValueError("safe area top+bottom must be smaller than height")

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "safe_area": self.safe_area.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualCanvas":
        safe_area_payload = data.get("safe_area", {})
        if not isinstance(safe_area_payload, dict):
            safe_area_payload = {}
        return cls(
            width=int(data.get("width", 1280)),
            height=int(data.get("height", 720)),
            safe_area=VisualSafeArea.from_dict(safe_area_payload),
        )


@dataclass(frozen=True)
class VisualBrand:
    template: str = "sie"
    primary_color: str = "#AD053D"
    font_family: str = "Microsoft YaHei"

    def to_dict(self) -> dict[str, str]:
        return {
            "template": self.template,
            "primary_color": self.primary_color,
            "font_family": self.font_family,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualBrand":
        return cls(
            template=str(data.get("template", "sie")).strip() or "sie",
            primary_color=str(data.get("primary_color", "#AD053D")).strip() or "#AD053D",
            font_family=str(data.get("font_family", "Microsoft YaHei")).strip() or "Microsoft YaHei",
        )


@dataclass(frozen=True)
class VisualIntent:
    audience: str = ""
    occasion: str = ""
    core_message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "audience": self.audience,
            "occasion": self.occasion,
            "core_message": self.core_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualIntent":
        return cls(
            audience=str(data.get("audience", "")).strip(),
            occasion=str(data.get("occasion", "")).strip(),
            core_message=str(data.get("core_message", "")).strip(),
        )


@dataclass(frozen=True)
class VisualLayout:
    type: str
    visual_focus: str = "center_claim"
    density: str = "medium"

    def __post_init__(self) -> None:
        if self.type not in SUPPORTED_LAYOUT_TYPES:
            raise ValueError(f"unsupported layout type: {self.type}")

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "visual_focus": self.visual_focus,
            "density": self.density,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualLayout":
        return cls(
            type=str(data.get("type", "")).strip(),
            visual_focus=str(data.get("visual_focus", "center_claim")).strip() or "center_claim",
            density=str(data.get("density", "medium")).strip() or "medium",
        )


@dataclass(frozen=True)
class VisualComponent:
    type: str
    role: str = ""
    text: str = ""
    label: str = ""
    value: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.type not in SUPPORTED_COMPONENT_TYPES:
            raise ValueError(f"unsupported component type: {self.type}")
        if self.type in {"headline", "subheadline", "hero_claim", "value_band", "footer_note"} and not self.text.strip():
            raise ValueError(f"component {self.type} requires non-empty text")
        if self.type in {"proof_card", "risk_card"} and not any(
            part.strip() for part in (self.text, self.label, self.value, self.detail)
        ):
            raise ValueError(f"component {self.type} requires non-empty card content")

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "role": self.role,
            "text": self.text,
            "label": self.label,
            "value": self.value,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualComponent":
        return cls(
            type=str(data.get("type", "")).strip(),
            role=str(data.get("role", "")).strip(),
            text=str(data.get("text", "")).strip(),
            label=str(data.get("label", "")).strip(),
            value=str(data.get("value", "")).strip(),
            detail=str(data.get("detail", "")).strip(),
        )


@dataclass(frozen=True)
class VisualSpec:
    slide_id: str
    layout: VisualLayout
    components: list[VisualComponent]
    schema_version: str = "0.1"
    canvas: VisualCanvas = field(default_factory=VisualCanvas)
    brand: VisualBrand = field(default_factory=VisualBrand)
    intent: VisualIntent = field(default_factory=VisualIntent)

    def __post_init__(self) -> None:
        if not self.slide_id.strip():
            raise ValueError("slide_id must not be empty")
        if not self.components:
            raise ValueError("components must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "slide_id": self.slide_id,
            "canvas": self.canvas.to_dict(),
            "brand": self.brand.to_dict(),
            "intent": self.intent.to_dict(),
            "layout": self.layout.to_dict(),
            "components": [component.to_dict() for component in self.components],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualSpec":
        canvas_payload = data.get("canvas", {})
        brand_payload = data.get("brand", {})
        intent_payload = data.get("intent", {})
        layout_payload = data.get("layout", {})
        component_payload = data.get("components", [])
        if not isinstance(canvas_payload, dict):
            canvas_payload = {}
        if not isinstance(brand_payload, dict):
            brand_payload = {}
        if not isinstance(intent_payload, dict):
            intent_payload = {}
        if not isinstance(layout_payload, dict):
            layout_payload = {}
        if not isinstance(component_payload, list):
            component_payload = []
        return cls(
            schema_version=str(data.get("schema_version", "0.1")).strip() or "0.1",
            slide_id=str(data.get("slide_id", "")).strip(),
            canvas=VisualCanvas.from_dict(canvas_payload),
            brand=VisualBrand.from_dict(brand_payload),
            intent=VisualIntent.from_dict(intent_payload),
            layout=VisualLayout.from_dict(layout_payload),
            components=[VisualComponent.from_dict(item) for item in component_payload if isinstance(item, dict)],
        )
