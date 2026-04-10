import unittest

from tools.sie_autoppt.v2.content_rewriter import rewrite_deck, rewrite_slide
from tools.sie_autoppt.v2.quality_checks import quality_gate
from tools.sie_autoppt.v2.schema import validate_deck_payload


class ContentRewriterTests(unittest.TestCase):
    def test_rewrite_deck_drops_duplicate_section_subtitle_after_title_rewrite(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "培训目标",
                        "subtitle": "帮助新任项目经理建立角色认知、动作框架和基本判断",
                    }
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slide = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"][0]
        self.assertEqual(rewritten_slide["title"], "帮助新任项目经理建立角色认知、动作框架和基本判断")
        self.assertIsNone(rewritten_slide["subtitle"])

    def test_rewrite_deck_rewrites_directory_style_titles_from_slide_content(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "建设背景",
                        "subtitle": "数据资产持续增长，治理机制需要从专项补丁转向平台化能力",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "two_columns",
                        "title": "现状问题",
                        "left": {
                            "heading": "业务侧问题",
                            "items": ["口径不统一，管理报表重复对数", "关键指标追溯链条不完整"],
                        },
                        "right": {
                            "heading": "技术侧问题",
                            "items": ["元数据与标准管理分散在多个系统"],
                        },
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slides = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"]
        self.assertEqual(rewritten_slides[0]["title"], "治理机制需要从专项补丁转向平台化能力")
        self.assertEqual(rewritten_slides[0]["subtitle"], "数据资产持续增长")
        self.assertEqual(rewritten_slides[1]["title"], "口径不统一，管理报表重复对数")
        self.assertEqual(rewritten_slides[1]["left"]["items"], ["关键指标追溯链条不完整"])
        self.assertGreaterEqual(rewrite_result.final_quality_gate.summary["warning_count"], 1)

    def test_rewrite_slide_compresses_title_content(self):
        gate_result = quality_gate(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "这是一个明显过长并且需要压缩表达的业务分析标题",
                        "content": [
                            "第一条内容明显过长，需要压缩到更适合页面承载的长度，并保留核心信息。",
                            "第二条内容也非常长，需要继续压缩表达。",
                            "第三条",
                            "第四条",
                            "第五条",
                            "第六条",
                            "第七条",
                        ],
                    }
                ],
            }
        )
        slide = gate_result.validated_deck.deck.model_dump(mode="json")["slides"][0]
        rewritten, actions = rewrite_slide(slide, list(gate_result.all_issues()))

        self.assertLessEqual(len(rewritten["title"]), len(slide["title"]))
        self.assertLessEqual(len(rewritten["content"]), 6)
        self.assertGreater(len(actions), 0)

    def test_rewrite_deck_rebalances_two_columns(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "two_columns",
                        "title": "双栏内容页",
                        "left": {
                            "heading": "左侧",
                            "items": ["事项一", "事项二", "事项三", "事项四", "事项五", "事项六"],
                        },
                        "right": {
                            "heading": "右侧",
                            "items": ["要点甲"],
                        },
                    }
                ],
            }
        )
        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slide = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"][0]
        self.assertLessEqual(len(rewritten_slide["left"]["items"]), 4)
        self.assertLessEqual(abs(len(rewritten_slide["left"]["items"]) - len(rewritten_slide["right"]["items"])), 3)

    def test_rewrite_keeps_safe_phrases_when_stripping_filler_words(self):
        gate_result = quality_gate(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "当前平台需要持续改进 CI/CD 交付链路并推动环境标准化",
                        "content": [
                            "当前团队需要持续改进 CI/CD 流程，并推动发布质量稳定提升。",
                            "第二条内容明显过长，需要继续压缩表达以适应页面宽度。",
                            "第三条",
                            "第四条",
                            "第五条",
                            "第六条",
                            "第七条",
                        ],
                    }
                ],
            }
        )
        slide = gate_result.validated_deck.deck.model_dump(mode="json")["slides"][0]
        rewritten, _ = rewrite_slide(slide, list(gate_result.all_issues()))

        self.assertIn("持续改进", rewritten["title"])
        self.assertTrue(any("CI/CD" in item for item in rewritten["content"]))

    def test_rewrite_deck_rewrites_generic_background_opening_title_from_subtitle(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "项目背景",
                        "subtitle": "预算受限下先聚焦高回报场景",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_only",
                        "title": "Next Step",
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slide = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"][0]
        self.assertEqual(rewritten_slide["title"], "预算受限下先聚焦高回报场景")
        self.assertIsNone(rewritten_slide["subtitle"])
        self.assertIn("rewrite_generic_opening_title", [action.action for action in rewrite_result.actions])

    def test_rewrite_deck_rewrites_repeated_title_from_slide_content(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "核心判断",
                        "subtitle": "先锁定高回报试点，再逐步扩大范围",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_content",
                        "title": "关键风险正在积累",
                        "content": ["流程割裂导致返工增加", "指标定义不一致导致管理失真"],
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_content",
                        "title": "关键风险正在积累",
                        "content": ["试点范围应锁定财务共享中心", "变革管理必须前置纳入预算"],
                    },
                    {
                        "slide_id": "s4",
                        "layout": "title_only",
                        "title": "Next Step",
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slides = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"]
        self.assertEqual(rewritten_slides[2]["title"], "试点范围应锁定财务共享中心")
        self.assertEqual(rewritten_slides[2]["content"], ["变革管理必须前置纳入预算"])
        self.assertIn("rewrite_repeated_title", [action.action for action in rewrite_result.actions])

    def test_rewrite_deck_removes_adjacent_repeated_content_fragments(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "核心判断",
                        "subtitle": "先统一口径，再启动流程自动化试点",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_content",
                        "title": "问题诊断",
                        "content": ["流程割裂导致返工增加", "指标定义不一致导致管理失真"],
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_content",
                        "title": "整改优先级已明确",
                        "content": [
                            "流程割裂导致返工增加",
                            "指标定义不一致导致管理失真",
                            "试点范围应锁定财务共享中心",
                        ],
                    },
                    {
                        "slide_id": "s4",
                        "layout": "title_only",
                        "title": "Next Step",
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slides = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"]
        self.assertEqual(rewritten_slides[2]["content"], ["试点范围应锁定财务共享中心"])
        self.assertIn("remove_adjacent_repeated_content", [action.action for action in rewrite_result.actions])

    def test_rewrite_deck_rewrites_generic_closing_page_to_next_step(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "核心判断",
                        "subtitle": "先统一口径，再启动流程自动化试点",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_content",
                        "title": "整改优先级已明确",
                        "content": ["试点范围应锁定财务共享中心", "变革管理必须前置纳入预算"],
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_only",
                        "title": "谢谢",
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slide = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"][-1]
        self.assertEqual(rewritten_slide["title"], "下一步：试点范围应锁定财务共享中心")
        self.assertEqual(rewrite_result.final_quality_gate.summary["high_count"], 0)
        self.assertFalse(
            any("generic closing or thanks" in issue.message for issue in rewrite_result.final_quality_gate.all_issues())
        )
        self.assertIn("rewrite_generic_closing_to_next_step", [action.action for action in rewrite_result.actions])

    def test_rewrite_deck_rewrites_non_action_ending_to_next_step(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "section_break",
                        "title": "核心判断",
                        "subtitle": "预算受限时先做高回报试点",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_content",
                        "title": "落地抓手",
                        "content": ["试点范围先锁定财务共享中心", "同步纳入变革管理预算"],
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_only",
                        "title": "总结",
                    },
                ],
            }
        )

        initial_gate = quality_gate(validated)
        rewrite_result = rewrite_deck(validated, initial_gate)

        self.assertTrue(rewrite_result.applied)
        rewritten_slide = rewrite_result.validated_deck.deck.model_dump(mode="json")["slides"][-1]
        self.assertEqual(rewritten_slide["title"], "下一步：试点范围先锁定财务共享中心")
        self.assertFalse(
            any("last slide does not clearly express" in issue.message for issue in rewrite_result.final_quality_gate.all_issues())
        )
        self.assertIn("rewrite_last_slide_to_next_step", [action.action for action in rewrite_result.actions])
