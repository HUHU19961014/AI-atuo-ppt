from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias, TypedDict
import json


class ProcessStepPayload(TypedDict):
    number: str
    title: str
    detail: str


class ProcessFlowPagePayload(TypedDict):
    steps: list[ProcessStepPayload]


class ArchitectureLayerPayload(TypedDict):
    label: str
    title: str
    detail: str


class SolutionArchitecturePagePayload(TypedDict, total=False):
    layers: list[ArchitectureLayerPayload]
    banner_text: str


class GovernanceCardPayload(TypedDict):
    label: str
    detail: str


class GovernancePagePayload(TypedDict, total=False):
    cards: list[GovernanceCardPayload]
    label_prefix: str
    footer_text: str


class ComparisonCardPayload(TypedDict):
    title: str
    detail: str


class ComparisonUpgradePagePayload(TypedDict, total=False):
    headline: str
    left_label: str
    right_label: str
    left_cards: list[ComparisonCardPayload]
    right_cards: list[ComparisonCardPayload]
    center_kicker: str
    center_title: str
    center_subtitle: str
    center_top_label: str
    center_section_title: str
    center_row1_left: str
    center_row1_right: str
    center_row2_left: str
    center_row2_right: str
    center_divider: str
    center_bottom_label: str
    center_bottom_title: str
    center_bottom_left: str
    center_bottom_right: str
    center_bottom_footer: str
    bottom_left_caption: str
    bottom_right_caption: str


class CapabilityRingItemPayload(TypedDict):
    title: str
    detail: str


class CapabilityRingPagePayload(TypedDict, total=False):
    items: list[CapabilityRingItemPayload]
    headline: str


class FivePhaseStagePayload(TypedDict):
    header: str
    tasks: list[str]


class FivePhasePathPagePayload(TypedDict):
    intro: str
    stages: list[FivePhaseStagePayload]
    legend: list[str]


class PainCardPayload(TypedDict, total=False):
    title: str
    detail: str
    points: list[str]


class PainCardsPagePayload(TypedDict, total=False):
    lead: str
    bottom_banner: str
    cards: list[PainCardPayload]


BodyPagePayload: TypeAlias = (
    SolutionArchitecturePagePayload
    | ProcessFlowPagePayload
    | GovernancePagePayload
    | ComparisonUpgradePagePayload
    | CapabilityRingPagePayload
    | FivePhasePathPagePayload
    | PainCardsPagePayload
    | dict[str, object]
)


@dataclass(frozen=True)
class HtmlSlide:
    title: str
    subtitle: str
    bullets: list[str]
    pattern_id: str = ""


@dataclass(frozen=True)
class InputPayload:
    title: str
    subtitle: str
    scope_title: str
    scope_subtitle: str
    focus_title: str
    focus_subtitle: str
    footer: str
    phases: list[dict[str, str]]
    scenarios: list[str]
    notes: list[str]
    slides: list[HtmlSlide] = field(default_factory=list)


@dataclass(frozen=True)
class StructureArgument:
    point: str
    evidence: str = ""


@dataclass(frozen=True)
class StructureSection:
    title: str
    key_message: str
    arguments: list[StructureArgument] = field(default_factory=list)


@dataclass(frozen=True)
class StructureSpec:
    core_message: str
    structure_type: str
    sections: list[StructureSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "core_message": self.core_message,
            "structure_type": self.structure_type,
            "sections": [
                {
                    "title": section.title,
                    "key_message": section.key_message,
                    "arguments": [
                        {
                            "point": argument.point,
                            "evidence": argument.evidence,
                        }
                        for argument in section.arguments
                    ],
                }
                for section in self.sections
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "StructureSpec":
        raw_sections = data.get("sections", [])
        sections: list[StructureSection] = []
        if isinstance(raw_sections, list):
            for raw_section in raw_sections:
                if not isinstance(raw_section, dict):
                    continue
                raw_arguments = raw_section.get("arguments", [])
                arguments: list[StructureArgument] = []
                if isinstance(raw_arguments, list):
                    for raw_argument in raw_arguments:
                        if not isinstance(raw_argument, dict):
                            continue
                        arguments.append(
                            StructureArgument(
                                point=str(raw_argument.get("point", "")).strip(),
                                evidence=str(raw_argument.get("evidence", "")).strip(),
                            )
                        )
                sections.append(
                    StructureSection(
                        title=str(raw_section.get("title", "")).strip(),
                        key_message=str(raw_section.get("key_message", "")).strip(),
                        arguments=arguments,
                    )
                )
        return cls(
            core_message=str(data.get("core_message", "")).strip(),
            structure_type=str(data.get("structure_type", "")).strip(),
            sections=sections,
        )


@dataclass(frozen=True)
class BodyPageSpec:
    page_key: str
    title: str
    subtitle: str
    bullets: list[str]
    pattern_id: str
    nav_title: str = ""
    reference_style_id: str | None = None
    payload: BodyPagePayload = field(default_factory=dict)
    layout_variant: str | None = None
    content_count: int = 0
    is_continuation: bool = False
    continuation_index: int | None = None
    slide_role: str | None = None
    layout_hints: dict[str, object] = field(default_factory=dict)
    source_item_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class DeckSpec:
    cover_title: str
    body_pages: list[BodyPageSpec]


@dataclass(frozen=True)
class DeckPlan:
    deck: DeckSpec
    chapter_lines: list[str]
    pattern_ids: list[str]


@dataclass(frozen=True)
class PageRenderTrace:
    page_key: str
    title: str
    requested_pattern_id: str
    actual_pattern_id: str
    reference_style_id: str | None = None
    render_route: str = ""
    fallback_reason: str = ""


@dataclass(frozen=True)
class DeckRenderTrace:
    input_kind: str
    body_render_mode: str
    reference_import_applied: bool
    reference_import_reason: str = ""
    preflight_notes: list[str] = field(default_factory=list)
    page_traces: list[PageRenderTrace] = field(default_factory=list)


@dataclass(frozen=True)
class GenerationArtifacts:
    output_path: Path
    deck_plan: DeckPlan
    render_trace: DeckRenderTrace
