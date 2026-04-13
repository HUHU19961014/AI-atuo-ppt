from functools import lru_cache
from importlib import import_module

from ..config import MAX_BODY_CHAPTERS
from ..inputs.html_parser import (
    parse_html_payload,
    validate_payload,
)
from ..models import BodyPagePayload, BodyPageSpec, DeckSpec, InputPayload
from ..patterns import infer_pattern
from ..template_manifest import TemplateStyleGuide, load_template_manifest
from .content_profiler import profile_bullets
from .layout_policy import resolve_layout_decision
from .pagination import paginate_body_page
from .payload_builders import (
    build_architecture_layers as shared_build_architecture_layers,
    build_claim_items as shared_build_claim_items,
    build_dashboard_insights as shared_build_dashboard_insights,
    build_generic_page_payload as shared_build_generic_page_payload,
    build_governance_cards as shared_build_governance_cards,
    build_kpi_metrics as shared_build_kpi_metrics,
    build_process_steps as shared_build_process_steps,
    build_risk_items as shared_build_risk_items,
    build_roadmap_stages as shared_build_roadmap_stages,
    derive_comparison_cards as shared_derive_comparison_cards,
)
from . import legacy_html_support as _legacy_html_support
from .text_utils import (
    compact_text as shared_compact_text,
    concise_text as shared_concise_text,
    short_stage_label as shared_short_stage_label,
    shorten_for_nav as shared_shorten_for_nav,
    split_title_detail as shared_split_title_detail,
)

shared_build_focus_bullets = _legacy_html_support.build_focus_bullets
shared_build_note_detail_bullets = _legacy_html_support.build_note_detail_bullets
shared_build_overview_bullets = _legacy_html_support.build_overview_bullets
shared_build_phase_detail_bullets = _legacy_html_support.build_phase_detail_bullets
shared_build_scope_bullets = _legacy_html_support.build_scope_bullets
shared_choose_page_pattern = _legacy_html_support.choose_page_pattern
shared_format_phase_summary = _legacy_html_support.format_phase_summary


DEFAULT_TITLE = "项目概览与阶段规划"
DEFAULT_SUBTITLE = "根据输入内容自动归纳重点，生成结构化业务汇报。"
DEFAULT_SCOPE_TITLE = "范围与关键场景"
DEFAULT_SCOPE_SUBTITLE = "根据输入场景自动归纳覆盖范围。"
DEFAULT_FOCUS_TITLE = "重点事项与验收标准"
DEFAULT_FOCUS_SUBTITLE = "根据输入要点自动生成关注事项。"
DEFAULT_PHASES_TITLE = "实施路径与阶段安排"
DEFAULT_PHASES_SUBTITLE = "按阶段梳理推进路径、关键动作与责任分工。"
DEFAULT_NOTES_TITLE = "风险提示与执行要求"
DEFAULT_NOTES_SUBTITLE = "沉淀需要重点关注的限制条件、风险和补充说明。"
DEFAULT_SUMMARY_TITLE = "总结"
DEFAULT_EMPTY_OVERVIEW = "补充 phase-* 内容后，可自动生成项目概览页。"
DEFAULT_EMPTY_SCOPE = "补充 scenario 内容后，可自动生成场景分析页。"
DEFAULT_EMPTY_FOCUS = "补充 note 或 footer 内容后，可自动生成重点事项页。"
DIRECTORY_WINDOW_SIZE = 5


@lru_cache(maxsize=1)
def _planning_style_context() -> tuple[TemplateStyleGuide, set[str], dict[str, tuple[dict[str, object], ...]]]:
    try:
        manifest = load_template_manifest()
    except (FileNotFoundError, ValueError):
        return TemplateStyleGuide(), set(), {}
    return manifest.style_guide, set(manifest.render_layouts.keys()), manifest.pattern_variants


def build_overview_bullets(payload: InputPayload) -> list[str]:
    return shared_build_overview_bullets(payload)


def build_scope_bullets(payload: InputPayload) -> list[str]:
    return shared_build_scope_bullets(payload)


def build_focus_bullets(payload: InputPayload) -> list[str]:
    return shared_build_focus_bullets(payload)


def clamp_requested_chapters(chapters: int | None, available_pages: int) -> int:
    requested = available_pages if chapters is None else int(chapters)
    if requested <= 0:
        requested = available_pages
    return max(1, min(requested, MAX_BODY_CHAPTERS, available_pages))


def infer_legacy_requested_chapters(payload: InputPayload) -> int:
    legacy_planner = import_module("tools.sie_autoppt.planning.legacy_html_planner")
    return legacy_planner.infer_legacy_requested_chapters(payload)


def build_phase_detail_bullets(payload: InputPayload) -> list[str]:
    return shared_build_phase_detail_bullets(payload)


def build_note_detail_bullets(payload: InputPayload) -> list[str]:
    return shared_build_note_detail_bullets(payload)


def format_phase_summary(phase: dict[str, str]) -> str:
    return shared_format_phase_summary(phase)


def split_title_detail(text: str) -> tuple[str, str]:
    return shared_split_title_detail(text)


def compact_text(text: str, max_chars: int) -> str:
    return shared_compact_text(text, max_chars)


def concise_text(text: str, max_chars: int) -> str:
    return shared_concise_text(text, max_chars)


def short_stage_label(text: str, max_chars: int = 8) -> str:
    return shared_short_stage_label(text, max_chars=max_chars)


def shorten_for_nav(text: str, max_chars: int = 10) -> str:
    return shared_shorten_for_nav(text, max_chars=max_chars)


def derive_comparison_cards(raw_items: list[str], fallback_title: str, synthetic_tail: tuple[str, str]) -> list[dict[str, str]]:
    return shared_derive_comparison_cards(raw_items, fallback_title, synthetic_tail)


def build_architecture_layers(payload: InputPayload) -> list[dict[str, str]]:
    return shared_build_architecture_layers(payload)


def build_process_steps(items: list[str]) -> list[dict[str, str]]:
    return shared_build_process_steps(items)


def build_governance_cards(items: list[str]) -> list[dict[str, str]]:
    return shared_build_governance_cards(items)


def build_roadmap_stages(items: list[str], max_items: int = 5) -> list[dict[str, str]]:
    return shared_build_roadmap_stages(items, max_items=max_items)


def build_kpi_metrics(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    return shared_build_kpi_metrics(items, max_items=max_items)


def build_dashboard_insights(items: list[str], max_items: int = 3) -> list[str]:
    return shared_build_dashboard_insights(items, max_items=max_items)


def build_risk_items(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    return shared_build_risk_items(items, max_items=max_items)


def build_claim_items(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    return shared_build_claim_items(items, max_items=max_items)


def resolve_requested_pattern(pattern_id: str, title: str, bullets: list[str]) -> str:
    return pattern_id or infer_pattern(title, bullets)



def resolve_page_layout(pattern_id: str, title: str, bullets: list[str]) -> tuple[str, str | None, dict[str, object], int]:
    style_guide, available_layout_variants, pattern_variants = _planning_style_context()
    content_profile = profile_bullets(bullets, thresholds=style_guide.density_thresholds)
    layout = resolve_layout_decision(
        requested_pattern_id=pattern_id,
        fallback_pattern_id=infer_pattern(title, bullets),
        content_profile=content_profile,
        preferred_item_counts=style_guide.preferred_item_counts,
        available_layout_variants=available_layout_variants,
        pattern_variants=pattern_variants,
    )
    return layout.pattern_id, layout.layout_variant, layout.layout_hints, layout.max_items_per_page



def build_body_page_spec(
    *,
    page_key: str,
    title: str,
    subtitle: str,
    bullets: list[str],
    pattern_id: str,
    nav_title: str = "",
    reference_style_id: str | None = None,
    payload: BodyPagePayload | None = None,
    layout_variant: str | None = None,
    slide_role: str | None = None,
    layout_hints: dict[str, object] | None = None,
    is_continuation: bool = False,
    continuation_index: int | None = None,
    source_item_range: tuple[int, int] | None = None,
) -> BodyPageSpec:
    return BodyPageSpec(
        page_key=page_key,
        title=title,
        subtitle=subtitle,
        bullets=bullets,
        pattern_id=pattern_id,
        nav_title=nav_title,
        reference_style_id=reference_style_id,
        payload=payload or {},
        layout_variant=layout_variant,
        content_count=len(bullets),
        is_continuation=is_continuation,
        continuation_index=continuation_index,
        slide_role=slide_role,
        layout_hints=layout_hints or {},
        source_item_range=source_item_range,
    )


def paginate_page_spec(page: BodyPageSpec, payload: InputPayload, max_items_per_page: int) -> list[BodyPageSpec]:
    paged = paginate_body_page(page, max_items_per_page=max_items_per_page)
    pages = []
    for chunk in paged:
        chunk_pattern_id, layout_variant, layout_hints, _ = resolve_page_layout(chunk.pattern_id, chunk.title, chunk.bullets)
        pages.append(
            build_body_page_spec(
                page_key=chunk.page_key,
                title=chunk.title,
                subtitle=chunk.subtitle,
                bullets=chunk.bullets,
                pattern_id=chunk_pattern_id,
                nav_title=chunk.nav_title,
                reference_style_id=chunk.reference_style_id,
                payload=build_generic_page_payload(chunk, chunk_pattern_id, payload),
                layout_variant=layout_variant,
                slide_role=chunk.slide_role,
                layout_hints={**chunk.layout_hints, **layout_hints, "page_item_count": len(chunk.bullets)},
                is_continuation=chunk.is_continuation,
                continuation_index=chunk.continuation_index,
                source_item_range=chunk.source_item_range,
            )
        )
    return pages


def build_generic_page_payload(page: BodyPageSpec, pattern_id: str, payload: InputPayload) -> BodyPagePayload:
    return shared_build_generic_page_payload(page, pattern_id, payload)


def choose_page_pattern(page_key: str, title: str, subtitle: str, bullets: list[str]) -> str:
    return shared_choose_page_pattern(page_key, title, subtitle, bullets) or infer_pattern(title, bullets)


def build_card_analysis_page_specs(html: str, chapters: int | None) -> DeckSpec | None:
    legacy_card = import_module("tools.sie_autoppt.planning.legacy_card_analysis")
    return legacy_card.build_card_analysis_page_specs(html, chapters)



def build_slide_tag_page_specs(payload: InputPayload, chapters: int | None) -> DeckSpec:
    page_specs = []
    for index, slide in enumerate(payload.slides, start=1):
        pattern_id, layout_variant, layout_hints, max_items_per_page = resolve_page_layout(slide.pattern_id, slide.title, slide.bullets)
        page = build_body_page_spec(
            page_key=f"slide_{index}",
            title=slide.title,
            subtitle=slide.subtitle,
            bullets=slide.bullets,
            pattern_id=pattern_id,
            nav_title=shorten_for_nav(slide.title),
            slide_role="body",
            layout_variant=layout_variant,
            layout_hints=layout_hints,
        )
        page_specs.extend(paginate_page_spec(page, payload, max_items_per_page))

    requested_chapters = clamp_requested_chapters(chapters, len(page_specs))
    cover_title = payload.title or (page_specs[0].title if page_specs else DEFAULT_TITLE)
    return DeckSpec(cover_title=cover_title, body_pages=page_specs[:requested_chapters])


def build_legacy_page_specs(payload: InputPayload, chapters: int | None) -> DeckSpec:
    legacy_planner = import_module("tools.sie_autoppt.planning.legacy_html_planner")
    return legacy_planner.build_legacy_page_specs(payload, chapters)


def build_deck_spec_from_html(html: str, chapters: int | None) -> DeckSpec:
    specialized_deck = build_card_analysis_page_specs(html, chapters)
    if specialized_deck:
        return specialized_deck

    payload = parse_html_payload(html)
    validate_payload(payload)

    if payload.slides:
        return build_slide_tag_page_specs(payload, chapters)
    return build_legacy_page_specs(payload, chapters)


def build_directory_lines(body_pages: list[BodyPageSpec]) -> list[str]:
    logical_pages = [page for page in body_pages if not page.is_continuation]
    lines = [page.nav_title or page.title for page in logical_pages[:DIRECTORY_WINDOW_SIZE]]
    for fallback in (DEFAULT_SUMMARY_TITLE, "Q&A"):
        if len(lines) >= DIRECTORY_WINDOW_SIZE:
            break
        lines.append(fallback)
    while len(lines) < DIRECTORY_WINDOW_SIZE:
        lines.append(f"章节{len(lines) + 1}")
    return lines[:DIRECTORY_WINDOW_SIZE]


def build_directory_window(body_pages: list[BodyPageSpec], active_index: int) -> tuple[list[str], int]:
    if not body_pages:
        lines = build_directory_lines([])
        return lines, 0

    logical_pages = [page for page in body_pages if not page.is_continuation]
    if not logical_pages:
        lines = build_directory_lines([])
        return lines, 0

    safe_active = max(0, min(active_index, len(body_pages) - 1))
    active_page = body_pages[safe_active]
    active_logical_index = 0
    for logical_index, page in enumerate(logical_pages):
        if page.page_key == active_page.page_key or (active_page.is_continuation and active_page.page_key.startswith(f"{page.page_key}_cont_")):
            active_logical_index = logical_index
            break

    labels = [page.nav_title or page.title for page in logical_pages]
    if len(labels) <= DIRECTORY_WINDOW_SIZE:
        lines = build_directory_lines(logical_pages)
        safe_index = max(0, min(active_logical_index, len(lines) - 1))
        return lines, safe_index

    max_start = len(labels) - DIRECTORY_WINDOW_SIZE
    start = min(max(active_logical_index - DIRECTORY_WINDOW_SIZE // 2, 0), max_start)
    window = labels[start : start + DIRECTORY_WINDOW_SIZE]
    return window, active_logical_index - start
