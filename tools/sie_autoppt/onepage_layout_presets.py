from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnePageLayoutPreset:
    preset_id: str
    label: str
    core_style: str
    use_case: str
    renderer_hints: dict[str, float | int | bool | str]


PRESETS: dict[str, OnePageLayoutPreset] = {
    "professional_modular_cards": OnePageLayoutPreset(
        preset_id="professional_modular_cards",
        label="专业模块化卡片型",
        core_style="咨询 / 软件公司标准呈现",
        use_case="通用咨询页、能力说明页、模块说明页",
        renderer_hints={
            "title_font_size": 22.0,
            "subtitle_font_size": 11.8,
            "summary_label_font_size": 13.0,
            "summary_intro_font_size": 13.2,
            "summary_headline_font_size": 18.8,
            "card_top": 2140000,
            "card_height": 2920000,
            "card_gap": 220000,
            "card_title_font_size": 17.5,
            "card_english_font_size": 8.8,
            "card_definition_font_size": 11.3,
            "card_bullet_font_size": 10.5,
            "footer_font_size": 10.2,
            "show_support_line": True,
        },
    ),
    "info_dense": OnePageLayoutPreset(
        preset_id="info_dense",
        label="信息密度型",
        core_style="信息完整但秩序清晰",
        use_case="研究页、方案论证页、专家讨论页",
        renderer_hints={
            "title_font_size": 21.5,
            "subtitle_font_size": 11.5,
            "summary_label_font_size": 12.8,
            "summary_intro_font_size": 12.8,
            "summary_headline_font_size": 18.2,
            "card_top": 2040000,
            "card_height": 3050000,
            "card_gap": 200000,
            "card_title_font_size": 17.0,
            "card_english_font_size": 8.5,
            "card_definition_font_size": 11.0,
            "card_bullet_font_size": 10.0,
            "footer_font_size": 10.0,
            "show_support_line": True,
        },
    ),
    "decision_oriented": OnePageLayoutPreset(
        preset_id="decision_oriented",
        label="决策导向型",
        core_style="结论先行，30 秒可扫读",
        use_case="老板汇报页、结论页、判断页",
        renderer_hints={
            "title_font_size": 22.5,
            "subtitle_font_size": 12.0,
            "summary_label_font_size": 13.0,
            "summary_intro_font_size": 13.5,
            "summary_headline_font_size": 20.0,
            "card_top": 2100000,
            "card_height": 2850000,
            "card_gap": 220000,
            "card_title_font_size": 18.0,
            "card_english_font_size": 9.0,
            "card_definition_font_size": 11.5,
            "card_bullet_font_size": 10.5,
            "footer_font_size": 10.4,
            "show_support_line": False,
        },
    ),
    "process_narrative": OnePageLayoutPreset(
        preset_id="process_narrative",
        label="流程叙事型",
        core_style="强逻辑线与阅读顺序",
        use_case="机制页、流程页、方法页",
        renderer_hints={
            "title_font_size": 21.8,
            "subtitle_font_size": 11.6,
            "summary_label_font_size": 12.8,
            "summary_intro_font_size": 13.0,
            "summary_headline_font_size": 18.5,
            "card_top": 2160000,
            "card_height": 2900000,
            "card_gap": 210000,
            "card_title_font_size": 17.2,
            "card_english_font_size": 8.6,
            "card_definition_font_size": 11.2,
            "card_bullet_font_size": 10.1,
            "footer_font_size": 10.2,
            "show_support_line": True,
        },
    ),
    "comparison_analysis": OnePageLayoutPreset(
        preset_id="comparison_analysis",
        label="对比分析型",
        core_style="差异清晰，结构对称",
        use_case="方案对比页、竞品对比页、选择页",
        renderer_hints={
            "title_font_size": 21.8,
            "subtitle_font_size": 11.6,
            "summary_label_font_size": 12.8,
            "summary_intro_font_size": 13.0,
            "summary_headline_font_size": 18.6,
            "card_top": 2120000,
            "card_height": 2880000,
            "card_gap": 220000,
            "card_title_font_size": 17.2,
            "card_english_font_size": 8.7,
            "card_definition_font_size": 11.1,
            "card_bullet_font_size": 10.2,
            "footer_font_size": 10.2,
            "show_support_line": True,
        },
    ),
    "status_reporting": OnePageLayoutPreset(
        preset_id="status_reporting",
        label="汇报型",
        core_style="客观、克制、状态优先",
        use_case="周会页、月报页、同步页",
        renderer_hints={
            "title_font_size": 21.6,
            "subtitle_font_size": 11.4,
            "summary_label_font_size": 12.6,
            "summary_intro_font_size": 12.8,
            "summary_headline_font_size": 18.0,
            "card_top": 2120000,
            "card_height": 2860000,
            "card_gap": 220000,
            "card_title_font_size": 17.0,
            "card_english_font_size": 8.5,
            "card_definition_font_size": 10.9,
            "card_bullet_font_size": 10.0,
            "footer_font_size": 10.0,
            "show_support_line": True,
        },
    ),
    "solution_story": OnePageLayoutPreset(
        preset_id="solution_story",
        label="解决方案型",
        core_style="问题 → 方法 → 价值",
        use_case="解决方案页、价值说明页",
        renderer_hints={
            "title_font_size": 22.0,
            "subtitle_font_size": 11.7,
            "summary_label_font_size": 12.8,
            "summary_intro_font_size": 13.0,
            "summary_headline_font_size": 19.0,
            "card_top": 2140000,
            "card_height": 2920000,
            "card_gap": 220000,
            "card_title_font_size": 17.5,
            "card_english_font_size": 8.8,
            "card_definition_font_size": 11.2,
            "card_bullet_font_size": 10.3,
            "footer_font_size": 10.2,
            "show_support_line": True,
        },
    ),
    "strategy_blueprint": OnePageLayoutPreset(
        preset_id="strategy_blueprint",
        label="战略蓝图型",
        core_style="高层视角，留白更主动",
        use_case="战略页、阶段规划页、愿景页",
        renderer_hints={
            "title_font_size": 22.2,
            "subtitle_font_size": 11.8,
            "summary_label_font_size": 12.8,
            "summary_intro_font_size": 13.0,
            "summary_headline_font_size": 18.8,
            "card_top": 2200000,
            "card_height": 2760000,
            "card_gap": 240000,
            "card_title_font_size": 17.4,
            "card_english_font_size": 8.8,
            "card_definition_font_size": 11.0,
            "card_bullet_font_size": 9.9,
            "footer_font_size": 10.0,
            "show_support_line": False,
        },
    ),
}


DEFAULT_ONEPAGE_PRESET_ID = "decision_oriented"


def get_onepage_layout_preset(preset_id: str | None = None) -> OnePageLayoutPreset:
    selected_id = (preset_id or DEFAULT_ONEPAGE_PRESET_ID).strip().lower()
    preset = PRESETS.get(selected_id)
    if preset is None:
        supported = ", ".join(sorted(PRESETS))
        raise KeyError(f"Unknown one-page layout preset: {selected_id}. Supported presets: {supported}")
    return preset


def list_onepage_layout_presets() -> tuple[OnePageLayoutPreset, ...]:
    return tuple(PRESETS[preset_id] for preset_id in sorted(PRESETS))
