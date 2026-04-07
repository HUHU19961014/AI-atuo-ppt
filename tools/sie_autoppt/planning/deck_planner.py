import re
from functools import lru_cache

from ..config import MAX_BODY_CHAPTERS
from ..inputs.html_parser import (
    clean_heading_text,
    extract_first_tag_text,
    extract_list_items_from_block,
    extract_steps,
    extract_tag_inside_block,
    extract_tag_with_class,
    parse_html_payload,
    validate_payload,
)
from ..models import BodyPagePayload, BodyPageSpec, DeckSpec, HtmlSlide, InputPayload
from ..patterns import infer_pattern
from ..template_manifest import TemplateStyleGuide, load_template_manifest
from .content_profiler import profile_bullets
from .layout_policy import resolve_layout_decision
from .pagination import paginate_body_page


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
DEFAULT_GOVERNANCE_LABEL = "重点"
DIRECTORY_WINDOW_SIZE = 5


@lru_cache(maxsize=1)
def _planning_style_context() -> tuple[TemplateStyleGuide, set[str]]:
    try:
        manifest = load_template_manifest()
    except (FileNotFoundError, ValueError):
        return TemplateStyleGuide(), set()
    return manifest.style_guide, set(manifest.render_layouts.keys())


def build_overview_bullets(payload: InputPayload) -> list[str]:
    bullets = [format_phase_summary(phase) for phase in payload.phases[:4] if format_phase_summary(phase)]
    if bullets:
        return bullets
    fallbacks = [item for item in (payload.subtitle, payload.footer) if item][:4]
    return fallbacks or [DEFAULT_EMPTY_OVERVIEW]


def build_scope_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.scenarios[:4]
    if bullets:
        return bullets
    phase_names = [phase["name"] for phase in payload.phases if phase["name"]][:4]
    return phase_names or [DEFAULT_EMPTY_SCOPE]


def build_focus_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.notes[:4]
    if payload.footer and payload.footer not in bullets:
        bullets.append(payload.footer)
    bullets = bullets[:4]
    return bullets or [DEFAULT_EMPTY_FOCUS]


def clamp_requested_chapters(chapters: int | None, available_pages: int) -> int:
    requested = available_pages if chapters is None else int(chapters)
    if requested <= 0:
        requested = available_pages
    return max(1, min(requested, MAX_BODY_CHAPTERS, available_pages))


def infer_legacy_requested_chapters(payload: InputPayload) -> int:
    weighted_chars = len(payload.title) + len(payload.subtitle) + len(payload.footer)
    weighted_chars += sum(len(item) for item in payload.scenarios)
    weighted_chars += sum(len(item) for item in payload.notes)
    weighted_chars += sum(
        len(phase.get("name", "")) + len(phase.get("func", "")) + len(phase.get("owner", ""))
        for phase in payload.phases
    )
    item_count = len(payload.phases) + len(payload.scenarios) + len(payload.notes)

    if item_count >= 10 or weighted_chars >= 260:
        return 5
    if item_count >= 6 or weighted_chars >= 140:
        return 4
    return 3


def build_phase_detail_bullets(payload: InputPayload) -> list[str]:
    bullets = [format_phase_summary(phase) for phase in payload.phases if format_phase_summary(phase)]
    if bullets:
        return bullets[:5]
    fallback = payload.scenarios[:5]
    return fallback or [DEFAULT_EMPTY_SCOPE]


def build_note_detail_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.notes[:5]
    if payload.footer and payload.footer not in bullets:
        bullets.append(payload.footer)
    bullets = bullets[:5]
    if bullets:
        return bullets
    fallback = payload.scenarios[4:9]
    return fallback or [DEFAULT_EMPTY_FOCUS]


def format_phase_summary(phase: dict[str, str]) -> str:
    prefix = phase.get("name", "")
    if phase.get("time"):
        prefix = f"{prefix} ({phase['time']})" if prefix else phase["time"]
    detail = phase.get("func") or phase.get("code") or phase.get("owner") or ""
    return f"{prefix}: {detail}".strip(": ").strip()


def split_title_detail(text: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    for sep in ("：", ":", " - ", " | "):
        if sep in normalized:
            title, detail = normalized.split(sep, 1)
            return title.strip(), detail.strip()
    return normalized, normalized


def compact_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip(" ,;，；。") + "…"


def concise_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    parts = [part.strip() for part in re.split(r"[。；;!?？!]", compact) if part.strip()]
    if not parts:
        return compact_text(compact, max_chars)
    candidate = parts[0]
    if len(parts) > 1 and len(candidate) + len(parts[1]) + 1 <= max_chars:
        candidate = f"{candidate}；{parts[1]}"
    return compact_text(candidate, max_chars)


def short_stage_label(text: str, max_chars: int = 8) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"\(.*?\)", "", compact)
    compact = re.sub(r"（.*?）", "", compact)
    return compact[:max_chars] if len(compact) > max_chars else compact


def shorten_for_nav(text: str, max_chars: int = 10) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = compact.replace("（", "").replace("）", "").replace("(", "").replace(")", "")
    return compact[:max_chars] if len(compact) > max_chars else compact


def derive_comparison_cards(raw_items: list[str], fallback_title: str, synthetic_tail: tuple[str, str]) -> list[dict[str, str]]:
    cards = []
    for item in raw_items:
        title, detail = split_title_detail(item)
        cards.append(
            {
                "title": compact_text(title or fallback_title, 14),
                "detail": concise_text(detail or title or fallback_title, 34),
            }
        )
    while len(cards) < 3:
        cards.append({"title": fallback_title, "detail": concise_text(fallback_title, 34)})
    cards = cards[:3]
    cards.append({"title": compact_text(synthetic_tail[0], 14), "detail": concise_text(synthetic_tail[1], 34)})
    return cards


def build_architecture_layers(payload: InputPayload) -> list[dict[str, str]]:
    layers = []
    for index, phase in enumerate(payload.phases[:4], start=1):
        title = compact_text(phase.get("name") or f"Layer {index}", 18)
        detail = concise_text(phase.get("func") or phase.get("code") or phase.get("owner") or title, 54)
        layers.append({"label": f"L{index:02d}", "title": title, "detail": detail})
    return layers


def build_process_steps(items: list[str]) -> list[dict[str, str]]:
    steps = []
    for index, item in enumerate(items[:4], start=1):
        title, detail = split_title_detail(item)
        compact_title = compact_text(title or f"Step {index}", 12)
        compact_detail = concise_text(detail or title or compact_title, 30)
        steps.append({"number": f"{index:02d}", "title": compact_title, "detail": compact_detail})
    return steps


def build_governance_cards(items: list[str]) -> list[dict[str, str]]:
    cards = []
    for index, item in enumerate(items[:4], start=1):
        title, detail = split_title_detail(item)
        label_source = title
        if title == detail:
            first_clause = re.split(r"[，、；。\s]", title, maxsplit=1)[0].strip()
            label_source = first_clause or title
        label = compact_text(label_source or f"{DEFAULT_GOVERNANCE_LABEL}{index}", 8)
        cards.append({"label": label, "detail": concise_text(detail or title or label, 40)})
    return cards


def resolve_requested_pattern(pattern_id: str, title: str, bullets: list[str]) -> str:
    return pattern_id or infer_pattern(title, bullets)



def resolve_page_layout(pattern_id: str, title: str, bullets: list[str]) -> tuple[str, str | None, dict[str, object], int]:
    style_guide, available_layout_variants = _planning_style_context()
    content_profile = profile_bullets(bullets, thresholds=style_guide.density_thresholds)
    layout = resolve_layout_decision(
        requested_pattern_id=pattern_id,
        fallback_pattern_id=infer_pattern(title, bullets),
        content_profile=content_profile,
        preferred_item_counts=style_guide.preferred_item_counts,
        available_layout_variants=available_layout_variants,
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
    page_items = page.bullets if page.page_key.startswith("slide_") else []
    if pattern_id == "solution_architecture":
        layers = [] if page_items else build_architecture_layers(payload)
        if layers:
            return {"layers": layers, "banner_text": compact_text(page.title, 16)}
        return {}
    if pattern_id == "process_flow":
        return {"steps": build_process_steps(page_items or payload.scenarios or page.bullets)}
    if pattern_id == "org_governance":
        payload_data: dict[str, object] = {
            "cards": build_governance_cards(page_items or payload.notes or page.bullets),
            "label_prefix": DEFAULT_GOVERNANCE_LABEL,
        }
        if payload.footer and not page_items:
            payload_data["footer_text"] = concise_text(payload.footer, 72)
        return payload_data
    return {}


def build_principle_items(success_bullets: list[str], steps: list[tuple[str, str]], conclusion: str) -> list[dict[str, str]]:
    items = []
    for item in success_bullets[:3]:
        title, detail = split_title_detail(item)
        items.append({"title": compact_text(title, 14), "detail": concise_text(detail, 28)})
    for title, detail in steps[:4]:
        items.append({"title": compact_text(short_stage_label(title, 10), 14), "detail": concise_text(detail, 28)})
    while len(items) < 7:
        items.append({"title": "协同交付", "detail": concise_text(conclusion or "固定结构，释放 AI 的内容创作空间。", 28)})
    return items[:7]


def build_pipeline_payload(steps: list[tuple[str, str]], conclusion: str, subtitle: str) -> dict[str, object]:
    default_stages = [
        ("阶段1\n业务抽象", ["梳理业务逻辑", "提炼关键信息", "统一输入结构", "输出标准数据", "明确渲染边界"]),
        ("阶段2\n组件沉淀", ["抽取复用组件", "沉淀原子能力", "约束版式规则", "绑定模板元素", "控制样式参数"]),
        ("阶段3\n自动渲染", ["批量生成页面", "写入目录导航", "完成基础 QA"]),
        ("阶段4\n人工抛光", ["分组与对齐", "视觉微调", "检查遮挡溢出", "补充动画过渡", "形成交付底稿"]),
        ("阶段5\n价值兑现", ["沉淀最佳实践", "回灌模板库", "兼顾效率与质量", "形成稳定交付闭环"]),
    ]

    stage_headers = []
    stage_tasks = []
    for index, (title, detail) in enumerate(steps[:4], start=1):
        stage_headers.append(f"阶段{index}\n{short_stage_label(title)}")
        sentence_parts = [part.strip() for part in re.split(r"[。；;!?？!]", detail) if part.strip()]
        tasks = [compact_text(part, 14) for part in sentence_parts[:5]]
        while len(tasks) < len(default_stages[index - 1][1]):
            tasks.append(default_stages[index - 1][1][len(tasks)])
        stage_tasks.append(tasks[: len(default_stages[index - 1][1])])

    while len(stage_headers) < 4:
        title, tasks = default_stages[len(stage_headers)]
        stage_headers.append(title)
        stage_tasks.append(tasks)

    stage_headers.append(default_stages[4][0])
    stage_tasks.append(default_stages[4][1])

    return {
        "intro": conclusion or subtitle,
        "stages": [{"header": header, "tasks": tasks} for header, tasks in zip(stage_headers[:5], stage_tasks[:5])],
        "legend": ["AI", "Python", "模板", "设计"],
    }


def choose_page_pattern(page_key: str, title: str, subtitle: str, bullets: list[str]) -> str:
    hint = f"{title} {subtitle}"
    if page_key == "overview" and any(keyword in hint for keyword in ("架构", "蓝图", "平台", "体系")):
        return "solution_architecture"
    if page_key == "scope" and any(keyword in hint for keyword in ("链路", "流程", "协同", "路径")):
        return "process_flow"
    if page_key == "focus" and any(keyword in hint for keyword in ("治理", "重点", "要求", "风险", "实施")):
        return "org_governance"
    return infer_pattern(title, bullets)


def build_card_analysis_page_specs(html: str, chapters: int | None) -> DeckSpec | None:
    if "comparison-grid" not in html or "pipeline-section" not in html:
        return None

    cover_title = extract_first_tag_text(html, "h1")
    subtitle = extract_tag_with_class(html, "p", "subtitle")
    danger_title = clean_heading_text(extract_tag_inside_block(html, "card card-danger", "h2"))
    danger_bullets = extract_list_items_from_block(html, "card card-danger")
    success_title = clean_heading_text(extract_tag_inside_block(html, "card card-success", "h2"))
    success_bullets = extract_list_items_from_block(html, "card card-success")
    pipeline_title = clean_heading_text(extract_tag_inside_block(html, "pipeline-section", "h2"))
    conclusion = extract_tag_with_class(html, "div", "conclusion")
    steps = extract_steps(html)

    if not any([cover_title, subtitle, danger_bullets, success_bullets, steps, conclusion]):
        return None

    comparison_payload = {
        "headline": subtitle or DEFAULT_SUBTITLE,
        "left_label": "一键生成式交付",
        "right_label": "工程化协同交付",
        "left_cards": derive_comparison_cards(
            danger_bullets,
            fallback_title="视觉风险",
            synthetic_tail=("调试成本放大", "长链路对话会放大排错和回归成本。"),
        ),
        "right_cards": derive_comparison_cards(
            success_bullets,
            fallback_title="工程化方案",
            synthetic_tail=("保留创作空间", conclusion or "固定骨架，让 AI 在内容与表达上创造增量价值。"),
        ),
        "center_kicker": "ENGINEERING COPILOT",
        "center_title": "结构化内容交付中枢",
        "center_subtitle": "内容引擎 · 模块化代码助理 · 人工视觉抛光",
        "center_top_label": "协同原则层",
        "center_section_title": "人机协同 (Human in the Loop)",
        "center_row1_left": "结构化输入",
        "center_row1_right": "模板化渲染",
        "center_row2_left": "视觉 QA",
        "center_row2_right": "人工微调",
        "center_divider": "先守住骨架，再释放 AI 创作空间",
        "center_bottom_label": "交付结果层",
        "center_bottom_title": "高质量输出 (Deliverable)",
        "center_bottom_left": "稳定复用",
        "center_bottom_right": "风格一致",
        "center_bottom_footer": "兼顾效率与质量",
        "bottom_left_caption": "识别边界",
        "bottom_right_caption": "交付升级",
    }

    principle_items = build_principle_items(success_bullets, steps, conclusion)
    page_specs = [
        build_body_page_spec(
            page_key="comparison_upgrade",
            title="能力边界与工程化解法",
            subtitle=subtitle or DEFAULT_SUBTITLE,
            bullets=(danger_bullets[:3] + success_bullets[:3]) or [DEFAULT_EMPTY_OVERVIEW],
            pattern_id="comparison_upgrade",
            nav_title=shorten_for_nav("能力边界对比"),
            reference_style_id="comparison_upgrade",
            payload=comparison_payload,
            slide_role="body",
        ),
        build_body_page_spec(
            page_key="practice_principles",
            title=success_title or "工程化实践原则",
            subtitle=conclusion or DEFAULT_SCOPE_SUBTITLE,
            bullets=[item["title"] for item in principle_items],
            pattern_id="capability_ring",
            nav_title=shorten_for_nav("实践原则"),
            reference_style_id="capability_ring",
            payload={"items": principle_items},
            slide_role="body",
        ),
        build_body_page_spec(
            page_key="delivery_pipeline",
            title=pipeline_title or "工业化流水线实施路径",
            subtitle=conclusion or DEFAULT_FOCUS_SUBTITLE,
            bullets=[f"{step_title}: {step_desc}" for step_title, step_desc in steps[:4]] or [DEFAULT_EMPTY_FOCUS],
            pattern_id="five_phase_path",
            nav_title=shorten_for_nav("实施路径"),
            reference_style_id="five_phase_path",
            payload=build_pipeline_payload(steps, conclusion, subtitle),
            slide_role="body",
        ),
    ]

    return DeckSpec(
        cover_title=cover_title or DEFAULT_TITLE,
        body_pages=page_specs[: clamp_requested_chapters(chapters, len(page_specs))],
    )


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
            bullets=build_overview_bullets(payload),
            pattern_id="general_business",
            nav_title=shorten_for_nav(payload.title or DEFAULT_TITLE),
            slide_role="body",
        ),
        build_body_page_spec(
            page_key="scope",
            title=scope_title,
            subtitle=scope_subtitle,
            bullets=build_scope_bullets(payload),
            pattern_id="general_business",
            nav_title=shorten_for_nav(scope_title),
            slide_role="body",
        ),
        build_body_page_spec(
            page_key="focus",
            title=focus_title,
            subtitle=focus_subtitle,
            bullets=build_focus_bullets(payload),
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
                bullets=build_phase_detail_bullets(payload),
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
                bullets=build_note_detail_bullets(payload),
                pattern_id="org_governance",
                nav_title=shorten_for_nav(DEFAULT_NOTES_TITLE),
                slide_role="body",
            )
        )

    inferred_chapters = infer_legacy_requested_chapters(payload)
    requested_chapters = clamp_requested_chapters(chapters if chapters is not None else inferred_chapters, len(candidate_pages))
    page_specs = candidate_pages[:requested_chapters]

    body_pages = []
    for page in page_specs:
        requested_pattern_id = choose_page_pattern(page.page_key, page.title, page.subtitle, page.bullets)
        pattern_id, layout_variant, layout_hints, max_items_per_page = resolve_page_layout(requested_pattern_id, page.title, page.bullets)
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
