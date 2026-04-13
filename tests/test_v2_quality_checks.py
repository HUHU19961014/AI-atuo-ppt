import unittest

from tools.sie_autoppt.v2.quality_checks import calculate_auto_score, check_deck_content
from tools.sie_autoppt.v2.schema import validate_deck_payload


class V2QualityChecksTests(unittest.TestCase):
    def test_language_consistency_warns_for_mixed_content(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "Language Mix",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "执行路径",
                        "content": ["Next step planning", "风险收敛"],
                    }
                ],
            }
        )
        warnings = check_deck_content(validated.deck)
        self.assertTrue(any("mixed-language content" in item.message for item in warnings))

    def test_directory_style_check_ignores_conclusion_titles(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "测试标题",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_only",
                        "title": "下月目标不是简单冲规模，而是提升重点客户推进质量",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_only",
                        "title": "Q2 的核心目标是守住利润率并恢复交付节奏",
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_only",
                        "title": "建设背景",
                    },
                ],
            }
        )

        warnings = check_deck_content(validated.deck)
        directory_style_warnings = [item.message for item in warnings if "directory-style" in item.message]
        directory_style_errors = [item for item in warnings if "directory-style" in item.message and item.warning_level == "error"]

        self.assertEqual(len(directory_style_warnings), 1)
        self.assertEqual(len(directory_style_errors), 1)
        self.assertIn("建设背景", directory_style_warnings[0])

    def test_directory_style_check_covers_extended_suffixes(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "测试标题",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_only",
                        "title": "治理现状",
                    },
                    {
                        "slide_id": "s2",
                        "layout": "title_only",
                        "title": "当前治理现状需要从分散整改转向平台化治理",
                    },
                ],
            }
        )

        warnings = check_deck_content(validated.deck)
        directory_style_warnings = [item.message for item in warnings if "directory-style" in item.message]
        directory_style_errors = [item for item in warnings if "directory-style" in item.message and item.warning_level == "error"]

        self.assertEqual(len(directory_style_warnings), 1)
        self.assertEqual(len(directory_style_errors), 1)
        self.assertIn("治理现状", directory_style_warnings[0])

    def test_content_checks_emit_structured_warnings(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "测试告警",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "这是一个明显过长而且超过二十四个汉字的标题用于测试",
                        "content": [
                            "第一条内容明显过长，用于验证单条 bullet 超过四十字符后的告警提示。",
                        ],
                    },
                    {
                        "slide_id": "s2",
                        "layout": "two_columns",
                        "title": "双栏页",
                        "left": {
                            "heading": "左栏",
                            "items": ["1", "2", "3", "4", "5", "6"],
                        },
                        "right": {
                            "heading": "右栏",
                            "items": ["1"],
                        },
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_image",
                        "title": "图片页",
                        "content": [
                            "第一条内容较长，用于校验 title_image 的长度告警机制是否生效。",
                            "第二条",
                            "第三条",
                            "第四条",
                            "第五条",
                        ],
                        "image": {"mode": "placeholder", "caption": "test"},
                    },
                ],
            }
        )

        warnings = check_deck_content(validated.deck)

        self.assertTrue(any(item.slide_id == "s1" and item.warning_level == "warning" for item in warnings))
        self.assertTrue(any("bullet items" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s2" and "left column" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s2" and "count gap" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s3" and "exceeds 4" in item.message for item in warnings))

    def test_auto_score_scales_penalty_by_slide_count(self):
        short_deck_score = calculate_auto_score(warning_count=4, high_count=1, error_count=0, slide_count=6)
        long_deck_score = calculate_auto_score(warning_count=4, high_count=1, error_count=0, slide_count=24)

        self.assertLess(short_deck_score.auto_score, long_deck_score.auto_score)

    def test_specialized_layouts_emit_density_warnings(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "Specialized",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "timeline",
                        "title": "实施路线",
                        "stages": [
                            {"title": "Q1", "detail": "A" * 46},
                            {"title": "Q2", "detail": "Build"},
                            {"title": "Q3", "detail": "Pilot"},
                            {"title": "Q4", "detail": "Scale"},
                            {"title": "Q5", "detail": "Govern"},
                            {"title": "Q6", "detail": "Optimize"},
                        ],
                    },
                    {
                        "slide_id": "s2",
                        "layout": "stats_dashboard",
                        "title": "KPI看板",
                        "metrics": [
                            {"label": "M1", "value": "1", "note": "n" * 36},
                            {"label": "M2", "value": "2"},
                            {"label": "M3", "value": "3"},
                            {"label": "M4", "value": "4"},
                            {"label": "M5", "value": "5"},
                        ],
                        "insights": ["i1", "i2", "i3", "i4"],
                    },
                    {
                        "slide_id": "s3",
                        "layout": "matrix_grid",
                        "title": "风险矩阵",
                        "cells": [
                            {"title": "Only", "body": "b" * 46},
                            {"title": "Second", "body": "ok"},
                        ],
                    },
                    {
                        "slide_id": "s4",
                        "layout": "cards_grid",
                        "title": "能力主题",
                        "cards": [
                            {"title": "A", "body": "b" * 36},
                            {"title": "B", "body": "ok"},
                            {"title": "C", "body": "ok"},
                            {"title": "D", "body": "ok"},
                        ],
                    },
                ],
            }
        )

        warnings = check_deck_content(validated.deck)

        self.assertTrue(any(item.slide_id == "s1" and "timeline has 6 stages" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s2" and "stats_dashboard has 5 metrics" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s3" and "matrix_grid has 2 cells" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s4" and "cards_grid has 4 cards" in item.message for item in warnings))

    def test_theme_must_use_sie_consulting_fixed(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "主题校验",
                    "theme": "business_red",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_only",
                        "title": "本页给出核心结论与下一步动作",
                    }
                ],
            }
        )

        warnings = check_deck_content(validated.deck)
        self.assertTrue(any(item.slide_id == "meta" and item.warning_level == "error" for item in warnings))
