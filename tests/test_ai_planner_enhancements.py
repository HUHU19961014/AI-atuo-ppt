import unittest

from tools.sie_autoppt.planning.ai_planner import (
    AiPlanningRequest,
    AiSlideBounds,
    build_ai_planning_prompts,
    build_deck_spec_from_ai_outline,
)


class AiPlannerEnhancementTests(unittest.TestCase):
    def test_build_ai_planning_prompts_include_clarified_context(self):
        developer_prompt, user_prompt = build_ai_planning_prompts(
            AiPlanningRequest(
                topic="帮我做Q2业绩汇报，5页，给公司领导看，商务专业风格",
                brief="重点讲增长数据、技术突破、下阶段计划",
            )
        )

        self.assertIn("Clarifier context", developer_prompt)
        self.assertIn("商务专业", user_prompt)
        self.assertIn("公司领导", user_prompt)
        self.assertIn("5", user_prompt)

    def test_build_deck_spec_from_ai_outline_builds_payload_for_complex_patterns(self):
        deck = build_deck_spec_from_ai_outline(
            {
                "cover_title": "AI AutoPPT 增强规划",
                "body_pages": [
                    {
                        "title": "现状与目标对比",
                        "subtitle": "明确升级方向",
                        "bullets": [
                            "当前流程: 协同链路长",
                            "当前数据: 口径不统一",
                            "目标流程: 形成闭环交付",
                            "目标数据: 建立统一底座",
                        ],
                        "pattern_id": "comparison_upgrade",
                        "nav_title": "对比",
                    },
                    {
                        "title": "核心能力",
                        "subtitle": "能力矩阵",
                        "bullets": [
                            "数据治理: 统一标准与口径",
                            "集成协同: 打通跨系统链路",
                            "运营分析: 支撑经营决策",
                        ],
                        "pattern_id": "capability_ring",
                        "nav_title": "能力",
                    },
                    {
                        "title": "实施路径",
                        "subtitle": "阶段化推进",
                        "bullets": [
                            "阶段一: 完成现状调研",
                            "阶段二: 搭建基础底座",
                            "阶段三: 推进试点上线",
                            "阶段四: 规模化复制",
                        ],
                        "pattern_id": "five_phase_path",
                        "nav_title": "路径",
                    },
                ],
            },
            slide_bounds=AiSlideBounds(min_slides=3, max_slides=3),
        )

        self.assertEqual(deck.body_pages[0].pattern_id, "comparison_upgrade")
        self.assertIn("left_cards", deck.body_pages[0].payload)
        self.assertIn("items", deck.body_pages[1].payload)
        self.assertIn("stages", deck.body_pages[2].payload)
