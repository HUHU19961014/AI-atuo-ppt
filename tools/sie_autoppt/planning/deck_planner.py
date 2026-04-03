import re

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
from ..models import BodyPageSpec, DeckSpec, InputPayload
from ..patterns import infer_pattern


DEFAULT_TITLE = "项目概览与UAT阶段计划"
DEFAULT_SUBTITLE = "根据输入 HTML 自动归纳测试章节与核心要点。"
DEFAULT_SCOPE_TITLE = "测试范围与关键场景"
DEFAULT_SCOPE_SUBTITLE = "根据输入场景自动归纳测试覆盖范围。"
DEFAULT_FOCUS_TITLE = "测试关注点与验收标准"
DEFAULT_FOCUS_SUBTITLE = "根据输入关注点自动生成验收提示。"
DEFAULT_SUMMARY_TITLE = "总结与行动"
DEFAULT_EMPTY_OVERVIEW = "补充 phase-* 内容后，可自动生成项目概览页。"
DEFAULT_EMPTY_SCOPE = "补充 scenario 内容后，可自动生成测试范围与关键场景页。"
DEFAULT_EMPTY_FOCUS = "补充 note 或 footer 内容后，可自动生成测试关注点与验收标准页。"


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


def clamp_requested_chapters(chapters: int, available_pages: int) -> int:
    return max(1, min(chapters, MAX_BODY_CHAPTERS, available_pages))


def format_phase_summary(phase: dict[str, str]) -> str:
    prefix = phase["name"]
    if phase["time"]:
        prefix = f"{prefix}（{phase['time']}）" if prefix else phase["time"]
    detail = phase["func"] or phase["code"] or phase["owner"]
    return f"{prefix}：{detail}".strip("：")


def split_title_detail(text: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    for sep in ("：", ":"):
        if sep in normalized:
            title, detail = normalized.split(sep, 1)
            return title.strip(), detail.strip()
    return normalized, normalized


def compact_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip(" ,;，；。)") + "…"


def concise_text(text: str, max_chars: int) -> str:
    parts = [part.strip() for part in re.split(r"[。；;，]", re.sub(r"\s+", " ", text)) if part.strip()]
    if not parts:
        return compact_text(text, max_chars)
    candidate = parts[0]
    if len(parts) > 1 and len(candidate) + len(parts[1]) + 1 <= max_chars:
        candidate = f"{candidate}，{parts[1]}"
    return compact_text(candidate, max_chars)


def short_stage_label(text: str, max_chars: int = 8) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"\(.*?\)", "", compact)
    compact = re.sub(r"（.*?）", "", compact)
    compact = compact.replace("最佳实践", "").replace("工业化流水线", "流水线")
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars]


def shorten_for_nav(text: str, max_chars: int = 10) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"（.*?）", "", compact)
    compact = compact.replace("(最佳实践)", "").replace("(V3.0战略视图)", "")
    compact = compact.replace("（", "").replace("）", "").replace("?", "")
    if len(compact) <= max_chars:
        return compact
    if "与" in compact:
        candidate = "与".join(compact.split("与")[:2])
        if len(candidate) <= max_chars:
            return candidate
    return compact[:max_chars]


def derive_comparison_cards(raw_items: list[str], fallback_title: str, synthetic_tail: tuple[str, str]) -> list[dict[str, str]]:
    cards = []
    for item in raw_items:
        title, detail = split_title_detail(item)
        cards.append(
            {
                "title": compact_text(title or fallback_title, 14),
                "detail": concise_text(detail or title, 34),
            }
        )
    while len(cards) < 3:
        cards.append(
            {
                "title": fallback_title,
                "detail": concise_text(fallback_title, 34),
            }
        )
    cards = cards[:3]
    cards.append({"title": compact_text(synthetic_tail[0], 14), "detail": concise_text(synthetic_tail[1], 34)})
    return cards


def build_principle_items(success_bullets: list[str], steps: list[tuple[str, str]], conclusion: str) -> list[dict[str, str]]:
    items = []
    for item in success_bullets[:3]:
        title, detail = split_title_detail(item)
        items.append({"title": compact_text(title, 14), "detail": concise_text(detail, 28)})
    for title, detail in steps[:4]:
        items.append({"title": compact_text(short_stage_label(title, 10), 14), "detail": concise_text(detail, 28)})
    while len(items) < 7:
        items.append({"title": "协同交付", "detail": concise_text(conclusion or "保持模板骨架稳定，给 AI 留出创作空间。", 28)})
    return items[:7]


def build_pipeline_payload(steps: list[tuple[str, str]], conclusion: str, subtitle: str) -> dict[str, object]:
    default_stages = [
        ("阶段一\n业务抽象", ["梳理业务逻辑", "提炼关键信息", "统一输入结构", "输出标准数据", "明确渲染边界"]),
        ("阶段二\n组件沉淀", ["抽取复用组件", "沉淀原子函数", "约束版式规则", "绑定模板元素", "控制样式参数"]),
        ("阶段三\n自动渲染", ["批量生成页面", "写入目录导航", "完成基础 QA"]),
        ("阶段四\n人工抛光", ["分组与对齐", "视觉微调", "检查遮挡溢出", "补充动画过渡", "形成交付底稿"]),
        ("阶段五\n价值兑现", ["沉淀最佳实践", "回灌模板库", "效率与质量兼得", "形成稳定交付闭环"]),
    ]
    stage_headers = []
    stage_tasks = []
    for index, (title, detail) in enumerate(steps[:4], start=1):
        stage_headers.append(f"阶段{index}\n{short_stage_label(title)}")
        sentence_parts = [part.strip() for part in re.split(r"[。；;，]", detail) if part.strip()]
        tasks = [compact_text(part, 14) for part in sentence_parts[:5]]
        while len(tasks) < len(default_stages[index - 1][1]):
            tasks.append(default_stages[index - 1][1][len(tasks)])
        stage_tasks.append(tasks[: len(default_stages[index - 1][1])])
    while len(stage_headers) < 4:
        title, tasks = default_stages[len(stage_headers)]
        stage_headers.append(title)
        stage_tasks.append(tasks)
    stage_headers.append("阶段五\n价值兑现")
    stage_tasks.append(default_stages[4][1])

    stages = []
    for header, tasks in zip(stage_headers[:5], stage_tasks[:5]):
        stages.append({"header": header, "tasks": tasks})

    return {
        "intro": conclusion or subtitle,
        "stages": stages,
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


def build_card_analysis_page_specs(html: str, chapters: int) -> DeckSpec | None:
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

    danger_cards = derive_comparison_cards(
        danger_bullets,
        fallback_title="视觉风险",
        synthetic_tail=("调试成本放大", "长链路对话会放大排错与回归成本。"),
    )
    success_cards = derive_comparison_cards(
        success_bullets,
        fallback_title="工程化解法",
        synthetic_tail=("保留创作空间", conclusion or "固定骨架，让 AI 在内容与表达上创造增量价值。"),
    )
    principle_items = build_principle_items(success_bullets, steps, conclusion)
    comparison_payload = {
        "headline": subtitle or "先识别能力边界，再设计工程化交付路径。",
        "left_label": "● 一键生成式交付",
        "right_label": "● 工程化协同交付",
        "left_cards": danger_cards,
        "right_cards": success_cards,
        "center_kicker": "ENGINEERING COPILOT",
        "center_title": "结构化内容交付中枢",
        "center_subtitle": "内容引擎 · 模块化代码助手 · 人工视觉抛光",
        "center_top_label": "协同原则层",
        "center_section_title": "人机协同 (Human in the Loop)",
        "center_row1_left": "结构化输入",
        "center_row1_right": "模板化渲染",
        "center_row2_left": "视觉 QA",
        "center_row2_right": "人工微调",
        "center_divider": "★ 先守住骨架，再释放 AI 创作空间 ★",
        "center_bottom_label": "交付结果层",
        "center_bottom_title": "高质量输出 (Deliverable)",
        "center_bottom_left": "稳定复用",
        "center_bottom_right": "风格一致",
        "center_bottom_footer": "效率与质量兼得",
        "bottom_left_caption": "识别边界",
        "bottom_right_caption": "交付升级",
    }

    page_specs = [
        BodyPageSpec(
            page_key="comparison_upgrade",
            title="能力边界与工程化解法",
            subtitle=subtitle or DEFAULT_SUBTITLE,
            bullets=(danger_bullets[:3] + success_bullets[:3]) or [DEFAULT_EMPTY_OVERVIEW],
            pattern_id="comparison_upgrade",
            nav_title=shorten_for_nav("能力边界对比"),
            reference_style_id="comparison_upgrade",
            payload=comparison_payload,
        ),
        BodyPageSpec(
            page_key="practice_principles",
            title=success_title or "工程化实践原则",
            subtitle=conclusion or DEFAULT_SCOPE_SUBTITLE,
            bullets=[item["title"] for item in principle_items],
            pattern_id="capability_ring",
            nav_title=shorten_for_nav("实践原则"),
            reference_style_id="capability_ring",
            payload={"items": principle_items},
        ),
        BodyPageSpec(
            page_key="delivery_pipeline",
            title=pipeline_title or "工业化流水线实施路径",
            subtitle=conclusion or DEFAULT_FOCUS_SUBTITLE,
            bullets=[f"{step_title}：{step_desc}" for step_title, step_desc in steps[:4]] or [DEFAULT_EMPTY_FOCUS],
            pattern_id="five_phase_path",
            nav_title=shorten_for_nav("实施路径"),
            reference_style_id="five_phase_path",
            payload=build_pipeline_payload(steps, conclusion, subtitle),
        ),
    ]
    return DeckSpec(
        cover_title=cover_title or DEFAULT_TITLE,
        body_pages=page_specs[: clamp_requested_chapters(chapters, len(page_specs))],
    )


def build_page_specs(payload: InputPayload, chapters: int) -> DeckSpec:
    requested_chapters = clamp_requested_chapters(chapters, 3)
    scope_title = payload.scope_title or DEFAULT_SCOPE_TITLE
    scope_subtitle = payload.scope_subtitle or DEFAULT_SCOPE_SUBTITLE
    focus_title = payload.focus_title or DEFAULT_FOCUS_TITLE
    focus_subtitle = payload.focus_subtitle or payload.footer or DEFAULT_FOCUS_SUBTITLE
    page_specs = [
        BodyPageSpec(
            page_key="overview",
            title=payload.title or DEFAULT_TITLE,
            subtitle=payload.subtitle or DEFAULT_SUBTITLE,
            bullets=build_overview_bullets(payload),
            pattern_id="general_business",
            nav_title=shorten_for_nav(payload.title or DEFAULT_TITLE),
        ),
        BodyPageSpec(
            page_key="scope",
            title=scope_title,
            subtitle=scope_subtitle,
            bullets=build_scope_bullets(payload),
            pattern_id="general_business",
            nav_title=shorten_for_nav(scope_title),
        ),
        BodyPageSpec(
            page_key="focus",
            title=focus_title,
            subtitle=focus_subtitle,
            bullets=build_focus_bullets(payload),
            pattern_id="general_business",
            nav_title=shorten_for_nav(focus_title),
        ),
    ][:requested_chapters]

    return DeckSpec(
        cover_title=payload.title or DEFAULT_TITLE,
        body_pages=[
            BodyPageSpec(
                page_key=page.page_key,
                title=page.title,
                subtitle=page.subtitle,
                bullets=page.bullets,
                pattern_id=choose_page_pattern(page.page_key, page.title, page.subtitle, page.bullets),
                nav_title=page.nav_title or shorten_for_nav(page.title),
            )
            for page in page_specs
        ],
    )


def build_deck_spec_from_html(html: str, chapters: int) -> DeckSpec:
    specialized_deck = build_card_analysis_page_specs(html, chapters)
    if specialized_deck:
        return specialized_deck
    payload = parse_html_payload(html)
    validate_payload(payload)
    return build_page_specs(payload, chapters)


def build_directory_lines(body_pages: list[BodyPageSpec]) -> list[str]:
    lines = [page.nav_title or page.title for page in body_pages[:5]]
    for fallback in (DEFAULT_SUMMARY_TITLE, "Q&A"):
        if len(lines) >= 5:
            break
        lines.append(fallback)
    while len(lines) < 5:
        lines.append(f"章节{len(lines) + 1}")
    return lines[:5]
