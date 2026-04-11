import unittest
from unittest.mock import patch

from tools.scenario_generators.sie_onepage_designer import (
    BulletItem,
    LawRow,
    OnePageBrief,
    TextFragment,
    resolve_onepage_strategy,
)
from tools.sie_autoppt.llm_openai import OpenAIConfigurationError


def _make_brief(*, title: str, process_steps: tuple[str, ...], row_title: str, right_title: str = "执行重点") -> OnePageBrief:
    return OnePageBrief(
        title=title,
        kicker="",
        summary_fragments=(TextFragment("这是一页测试内容。"),),
        law_rows=(
            LawRow(
                number="01",
                title=row_title,
                badge="测试",
                badge_red=False,
                runs=(TextFragment("测试内容"), TextFragment("补充说明")),
            ),
        ),
        right_kicker="EXECUTION VIEW",
        right_title=right_title,
        process_steps=process_steps,
        right_bullets=(BulletItem("重点：", "用于测试自动版式选择。"),),
        strategy_title="建议",
        strategy_fragments=(TextFragment("建议内容"),),
        footer="footer",
        page_no="01",
        required_terms=("测试",),
        variant="auto",
        layout_strategy="auto",
    )


class _FakeClient:
    def __init__(self, _config):
        pass

    def create_structured_json(self, developer_prompt, user_prompt, schema_name, schema):
        return {
            "strategy_id": "comparison_decision",
            "rationale": "内容包含明确方案对比与取舍判断，应采用对比决策型版式。",
        }


class SieOnepageStrategyTests(unittest.TestCase):
    def test_auto_strategy_falls_back_to_process_storyline_without_ai_key(self):
        brief = _make_brief(
            title="文件上传闭环流程",
            row_title="执行要求",
            process_steps=("发起", "归集", "校验", "上传", "留痕"),
        )

        with patch(
            "tools.scenario_generators.sie_onepage_designer.load_openai_responses_config",
            side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
        ):
            resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "heuristic")
        self.assertEqual(selection.strategy_id, "process_storyline")
        self.assertEqual(resolved_brief.variant, "signal_band")

    def test_auto_strategy_can_use_ai_choice_when_available(self):
        brief = _make_brief(
            title="供应商方案对比与选型建议",
            row_title="方案A vs 方案B",
            process_steps=("识别", "评估"),
            right_title="对比后做出选择",
        )

        with patch("tools.scenario_generators.sie_onepage_designer.load_openai_responses_config", return_value=object()):
            with patch("tools.scenario_generators.sie_onepage_designer.OpenAIResponsesClient", side_effect=_FakeClient):
                resolved_brief, selection = resolve_onepage_strategy(brief, model="test-model")

        self.assertEqual(selection.source, "ai")
        self.assertEqual(selection.strategy_id, "comparison_decision")
        self.assertEqual(resolved_brief.variant, "comparison_split")

    def test_explicit_variant_skips_auto_selection(self):
        brief = _make_brief(
            title="老板汇报总结",
            row_title="总结",
            process_steps=("识别", "评估"),
        )
        brief = OnePageBrief(**{**brief.__dict__, "variant": "asymmetric_focus", "layout_strategy": ""})

        resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "manual")
        self.assertEqual(selection.layout_variant, "asymmetric_focus")
        self.assertEqual(resolved_brief.variant, "asymmetric_focus")

    def test_explicit_layout_strategy_id_skips_ai_and_heuristic(self):
        brief = _make_brief(
            title="Sales proof layout",
            row_title="Proof points",
            process_steps=("Identify", "Evaluate"),
        )
        brief = OnePageBrief(**{**brief.__dict__, "layout_strategy": "evidence_dense_brief"})

        resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "manual")
        self.assertEqual(selection.strategy_id, "evidence_dense_brief")
        self.assertEqual(selection.layout_variant, "balanced_dual_panel")
        self.assertEqual(resolved_brief.variant, "balanced_dual_panel")

    def test_explicit_layout_variant_in_layout_strategy_is_respected(self):
        brief = _make_brief(
            title="Sales proof layout",
            row_title="Proof points",
            process_steps=("Identify", "Evaluate"),
        )
        brief = OnePageBrief(**{**brief.__dict__, "layout_strategy": "comparison_split"})

        resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "manual")
        self.assertEqual(selection.strategy_id, "manual_variant")
        self.assertEqual(selection.layout_variant, "comparison_split")
        self.assertEqual(resolved_brief.variant, "comparison_split")

    def test_auto_strategy_can_pick_timeline_layout_for_roadmap_content(self):
        brief = _make_brief(
            title="年度推进路线图",
            row_title="阶段里程碑",
            process_steps=("Q1启动", "Q2落地", "Q3扩展", "Q4固化"),
            right_title="按季度推进的实施路线图",
        )

        with patch(
            "tools.scenario_generators.sie_onepage_designer.load_openai_responses_config",
            side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
        ):
            resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "heuristic")
        self.assertEqual(selection.strategy_id, "roadmap_milestones")
        self.assertEqual(resolved_brief.variant, "timeline_vertical")

    def test_status_dashboard_priority_can_override_generic_process_steps(self):
        brief = _make_brief(
            title="文件上传责任人与时限看板",
            row_title="责任人状态",
            process_steps=("ERP发货", "ERP送货", "资料归集", "赛意上传", "批次留痕"),
            right_title="一页看清责任、时限与跟进动作",
        )

        with patch(
            "tools.scenario_generators.sie_onepage_designer.load_openai_responses_config",
            side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
        ):
            resolved_brief, selection = resolve_onepage_strategy(brief)

        self.assertEqual(selection.source, "heuristic")
        self.assertEqual(selection.strategy_id, "status_dashboard")
        self.assertEqual(resolved_brief.variant, "summary_board")


if __name__ == "__main__":
    unittest.main()
