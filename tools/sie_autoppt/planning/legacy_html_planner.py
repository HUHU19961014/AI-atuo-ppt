from ..models import DeckSpec, InputPayload
from .deck_planner import (
    DEFAULT_FOCUS_SUBTITLE,
    DEFAULT_FOCUS_TITLE,
    DEFAULT_NOTES_SUBTITLE,
    DEFAULT_NOTES_TITLE,
    DEFAULT_PHASES_SUBTITLE,
    DEFAULT_PHASES_TITLE,
    DEFAULT_SCOPE_SUBTITLE,
    DEFAULT_SCOPE_TITLE,
    DEFAULT_SUBTITLE,
    DEFAULT_TITLE,
    build_body_page_spec,
    clamp_requested_chapters,
    paginate_page_spec,
    resolve_page_layout,
)
from . import legacy_html_support as _legacy_html_support
from .payload_builders import build_generic_page_payload
from .text_utils import shorten_for_nav


def build_legacy_page_specs(payload: InputPayload, chapters: int | None) -> DeckSpec:
    candidate_pages = []
    scope_title = payload.scope_title or DEFAULT_SCOPE_TITLE
    scope_subtitle = payload.scope_subtitle or DEFAULT_SCOPE_SUBTITLE
    focus_title = payload.focus_title or DEFAULT_FOCUS_TITLE
    focus_subtitle = payload.focus_subtitle or payload.footer or DEFAULT_FOCUS_SUBTITLE
    candidate_pages.extend(
        [
            build_body_page_spec(
                page_key="overview",
                title=payload.title or DEFAULT_TITLE,
                subtitle=payload.subtitle or DEFAULT_SUBTITLE,
                bullets=_legacy_html_support.build_overview_bullets(payload),
                pattern_id="general_business",
                nav_title=shorten_for_nav(payload.title or DEFAULT_TITLE),
                slide_role="body",
            ),
            build_body_page_spec(
                page_key="scope",
                title=scope_title,
                subtitle=scope_subtitle,
                bullets=_legacy_html_support.build_scope_bullets(payload),
                pattern_id="general_business",
                nav_title=shorten_for_nav(scope_title),
                slide_role="body",
            ),
            build_body_page_spec(
                page_key="focus",
                title=focus_title,
                subtitle=focus_subtitle,
                bullets=_legacy_html_support.build_focus_bullets(payload),
                pattern_id="general_business",
                nav_title=shorten_for_nav(focus_title),
                slide_role="body",
            ),
        ]
    )

    if payload.phases and (len(payload.phases) >= 4 or len(payload.scenarios) >= 4):
        candidate_pages.append(
            build_body_page_spec(
                page_key="phases",
                title=DEFAULT_PHASES_TITLE,
                subtitle=DEFAULT_PHASES_SUBTITLE,
                bullets=_legacy_html_support.build_phase_detail_bullets(payload),
                pattern_id="process_flow",
                nav_title=shorten_for_nav(DEFAULT_PHASES_TITLE),
                slide_role="body",
            )
        )

    if payload.notes or payload.footer:
        candidate_pages.append(
            build_body_page_spec(
                page_key="notes",
                title=DEFAULT_NOTES_TITLE,
                subtitle=DEFAULT_NOTES_SUBTITLE,
                bullets=_legacy_html_support.build_note_detail_bullets(payload),
                pattern_id="org_governance",
                nav_title=shorten_for_nav(DEFAULT_NOTES_TITLE),
                slide_role="body",
            )
        )

    inferred_chapters = _legacy_html_support.infer_legacy_requested_chapters(payload)
    requested_chapters = clamp_requested_chapters(chapters if chapters is not None else inferred_chapters, len(candidate_pages))
    page_specs = candidate_pages[:requested_chapters]

    body_pages = []
    for page in page_specs:
        requested_pattern_id = _legacy_html_support.choose_page_pattern(page.page_key, page.title, page.subtitle, page.bullets)
        pattern_id, layout_variant, layout_hints, max_items_per_page = resolve_page_layout(
            requested_pattern_id,
            page.title,
            page.bullets,
        )
        planned_page = build_body_page_spec(
            page_key=page.page_key,
            title=page.title,
            subtitle=page.subtitle,
            bullets=page.bullets,
            pattern_id=pattern_id,
            nav_title=page.nav_title or shorten_for_nav(page.title),
            payload=build_generic_page_payload(page, pattern_id, payload),
            slide_role=page.slide_role,
            layout_variant=layout_variant,
            layout_hints=layout_hints,
        )
        body_pages.extend(paginate_page_spec(planned_page, payload, max_items_per_page))

    return DeckSpec(cover_title=payload.title or DEFAULT_TITLE, body_pages=body_pages)


infer_legacy_requested_chapters = _legacy_html_support.infer_legacy_requested_chapters

__all__ = ["build_legacy_page_specs", "infer_legacy_requested_chapters"]
