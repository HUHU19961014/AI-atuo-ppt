import re

from ..inputs.html_parser import (
    clean_heading_text,
    extract_first_tag_text,
    extract_list_items_from_block,
    extract_steps,
    extract_tag_inside_block,
    extract_tag_with_class,
)
from ..models import DeckSpec
from .payload_builders import derive_comparison_cards
from .text_utils import compact_text, concise_text, short_stage_label


def build_principle_items(success_bullets: list[str], steps: list[tuple[str, str]], conclusion: str) -> list[dict[str, str]]:
    from .deck_planner import split_title_detail

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
        ("阶段1\n业务抽象", ["梳理业务逻辑", "提炼关键信息", "统一输入结构", "输出标准数据", "明确演绎边界"]),
        ("阶段2\n组件沉淀", ["抽取复用组件", "沉淀原子能力", "约束版式规则", "绑定模板元素", "控制样式参数"]),
        ("阶段3\n自动演绎", ["批量生成页面", "写入目录导航", "完成基础 QA"]),
        ("阶段4\n人工抛光", ["分组与对齐", "视觉微调", "检查遮挡溢出", "补充动画过渡", "形成交付底稿"]),
        ("阶段5\n价值兑现", ["沉淀最佳实践", "回灌模板库", "兼顾效率与质量", "形成稳定交付闭环"]),
    ]

    stage_headers = []
    stage_tasks = []
    for index, (title, detail) in enumerate(steps[:4], start=1):
        stage_headers.append(f"阶段{index}\n{short_stage_label(title)}")
        sentence_parts = [part.strip() for part in re.split(r"[銆傦紱;!?锛?]", detail) if part.strip()]
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


def build_card_analysis_page_specs(html: str, chapters: int | None) -> DeckSpec | None:
    from .deck_planner import (
        DEFAULT_EMPTY_FOCUS,
        DEFAULT_SCOPE_SUBTITLE,
        DEFAULT_SUBTITLE,
        DEFAULT_TITLE,
        build_body_page_spec,
        clamp_requested_chapters,
        shorten_for_nav,
    )

    if "comparison-grid" not in html or "pipeline-section" not in html:
        return None

    cover_title = extract_first_tag_text(html, "h1")
    subtitle = extract_tag_with_class(html, "p", "subtitle")
    _ = clean_heading_text(extract_tag_inside_block(html, "card card-danger", "h2"))
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
        "center_subtitle": "内容引擎 路 模块化代码助手 路 人工视觉抛光",
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
            bullets=(danger_bullets[:3] + success_bullets[:3]) or [DEFAULT_EMPTY_FOCUS],
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
            subtitle=conclusion or DEFAULT_SCOPE_SUBTITLE,
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


__all__ = ["build_card_analysis_page_specs", "build_pipeline_payload", "build_principle_items"]
