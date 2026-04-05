from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias, TypedDict


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
    page_traces: list[PageRenderTrace] = field(default_factory=list)


@dataclass(frozen=True)
class GenerationArtifacts:
    output_path: Path
    deck_plan: DeckPlan
    render_trace: DeckRenderTrace
