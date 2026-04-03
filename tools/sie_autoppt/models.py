from dataclasses import dataclass, field


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
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DeckSpec:
    cover_title: str
    body_pages: list[BodyPageSpec]


@dataclass(frozen=True)
class DeckPlan:
    deck: DeckSpec
    chapter_lines: list[str]
    pattern_ids: list[str]
