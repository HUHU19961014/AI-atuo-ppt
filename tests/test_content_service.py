import unittest

from tools.sie_autoppt.content_service import build_deck_spec_from_structure, map_structure_to_slide_schema
from tools.sie_autoppt.models import StructureArgument, StructureSection, StructureSpec


class ContentServiceTests(unittest.TestCase):
    def test_map_structure_to_slide_schema_detects_process_and_comparison(self):
        process_schema = map_structure_to_slide_schema(
            structure_type="solution_design",
            title="三阶段推进路径",
            key_message="按阶段推进以降低风险",
            arguments=[StructureArgument(point="阶段一"), StructureArgument(point="阶段二")],
        )
        comparison_schema = map_structure_to_slide_schema(
            structure_type="comparison_analysis",
            title="现状与目标对比",
            key_message="从旧模式切换到新模式",
            arguments=[
                StructureArgument(point="旧模式成本高"),
                StructureArgument(point="旧模式协同慢"),
                StructureArgument(point="新模式自动化更强"),
                StructureArgument(point="新模式治理更清晰"),
            ],
        )

        self.assertEqual(process_schema, "process")
        self.assertEqual(comparison_schema, "comparison")

    def test_build_deck_spec_from_structure_preserves_structure_order(self):
        structure = StructureSpec(
            core_message="AI 商业化需要从价值验证走向规模复制",
            structure_type="strategy_report",
            sections=[
                StructureSection(
                    title="核心结论",
                    key_message="先验证价值，再放大组织能力",
                    arguments=[
                        StructureArgument(point="先锁定高价值场景", evidence="避免范围失控"),
                        StructureArgument(point="先建立交付机制", evidence="保证复制效率"),
                    ],
                ),
                StructureSection(
                    title="实施路径",
                    key_message="按三阶段推进落地",
                    arguments=[
                        StructureArgument(point="试点验证", evidence="验证业务收益"),
                        StructureArgument(point="流程嵌入", evidence="打通协同接口"),
                        StructureArgument(point="规模复制", evidence="形成标准机制"),
                    ],
                ),
            ],
        )

        deck = build_deck_spec_from_structure(structure, topic="AI 商业化路径分析")

        self.assertEqual(deck.cover_title, "AI 商业化路径分析")
        self.assertEqual([page.title for page in deck.body_pages], ["核心结论", "实施路径"])
        self.assertEqual(deck.body_pages[0].layout_hints["slide_schema"], "conclusion")
        self.assertEqual(deck.body_pages[1].layout_hints["slide_schema"], "process")
        self.assertEqual(deck.body_pages[1].pattern_id, "process_flow")
        self.assertEqual(deck.body_pages[1].payload["steps"][0]["title"], "试点验证")
