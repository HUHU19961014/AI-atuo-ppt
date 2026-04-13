import unittest

from tools.sie_autoppt.v2.deck_director import compile_semantic_deck_payload, plan_semantic_slide_layout
from tools.sie_autoppt.v2.semantic_schema_builder import BLOCK_KIND_SCHEMAS, SUPPORTED_BLOCK_KINDS, build_semantic_deck_schema


class V2DeckDirectorTests(unittest.TestCase):
    def test_supported_block_kinds_are_derived_from_schema_registry(self):
        self.assertEqual(tuple(BLOCK_KIND_SCHEMAS), SUPPORTED_BLOCK_KINDS)
        schema = build_semantic_deck_schema()
        block_variants = schema["properties"]["slides"]["items"]["properties"]["blocks"]["items"]["anyOf"]
        self.assertEqual(SUPPORTED_BLOCK_KINDS, tuple(variant["properties"]["kind"]["const"] for variant in block_variants))

    def test_plan_semantic_slide_layout_prefers_title_content_for_simple_narrative(self):
        plan = plan_semantic_slide_layout(
            {
                "slide_id": "s1",
                "title": "项目背景",
                "intent": "narrative",
                "blocks": [{"kind": "bullets", "items": ["说明业务背景", "界定本次范围", "确认关键约束"]}],
            }
        )

        self.assertEqual(plan.layout, "title_content")
        self.assertEqual(plan.reason, "default-content")

    def test_compile_comparison_slide_to_two_columns(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "当前与目标",
                        "intent": "comparison",
                        "blocks": [
                            {
                                "kind": "comparison",
                                "left_heading": "当前",
                                "left_items": ["流程分散", "响应慢"],
                                "right_heading": "目标",
                                "right_items": ["流程打通", "响应快"],
                            }
                        ],
                    }
                ],
            }
        )
        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "two_columns")
        self.assertEqual(slide.left.heading, "当前")
        self.assertEqual(slide.right.heading, "目标")

    def test_compile_framework_with_image_block_to_title_image(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "能力框架",
                        "intent": "framework",
                        "key_message": "四层能力共同支撑转型落地。",
                        "blocks": [
                            {"kind": "image", "mode": "placeholder", "caption": "框架示意"},
                            {"kind": "bullets", "items": ["业务层", "数据层", "平台层"]},
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "title_image")
        self.assertEqual(slide.image.mode, "placeholder")
        self.assertIn("四层能力共同支撑转型落地。", slide.content)

    def test_compile_dense_analysis_to_paginated_title_content(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "关键举措",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "bullets",
                                "heading": "措施",
                                "items": ["措施一", "措施二", "措施三", "措施四", "措施五", "措施六", "措施七"],
                            }
                        ],
                    }
                ],
            }
        )
        self.assertGreaterEqual(len(validated.deck.slides), 2)
        for slide in validated.deck.slides:
            self.assertEqual(slide.layout, "title_content")
            self.assertLessEqual(len(slide.content), 6)

    def test_compile_conclusion_statement_to_title_only(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "结论",
                        "intent": "conclusion",
                        "blocks": [{"kind": "statement", "text": "先打通主链，再扩展到运营闭环。"}],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "title_only")
        self.assertEqual(slide.title, "先打通主链，再扩展到运营闭环。")


    def test_compile_cards_pair_to_two_columns(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Core Capabilities",
                        "intent": "framework",
                        "blocks": [
                            {
                                "kind": "cards",
                                "cards": [
                                    {"title": "Plan", "body": "Drive aligned decisions"},
                                    {"title": "Execute", "body": "Stabilize delivery control"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "two_columns")
        self.assertEqual(slide.left.heading, "Plan")
        self.assertEqual(slide.right.heading, "Execute")

    def test_compile_stats_pair_to_two_columns(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "KPI Snapshot",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "stats",
                                "metrics": [
                                    {"label": "OTD", "value": "95%", "note": "Target >=93%"},
                                    {"label": "Yield", "value": "98%", "note": "Stable month-on-month"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "two_columns")
        self.assertEqual(slide.left.heading, "OTD")
        self.assertEqual(slide.right.heading, "Yield")

    def test_compile_timeline_dense_to_two_columns(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Roadmap",
                        "intent": "narrative",
                        "blocks": [
                            {
                                "kind": "timeline",
                                "stages": [
                                    {"title": "Q1", "detail": "Scope and align"},
                                    {"title": "Q2", "detail": "Build core workflows"},
                                    {"title": "Q3", "detail": "Scale pilot"},
                                    {"title": "Q4", "detail": "Roll out governance"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "timeline")
        self.assertEqual(len(slide.stages), 4)

    def test_compile_matrix_block_to_two_columns(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Risk Matrix",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "matrix",
                                "x_axis": "Impact",
                                "y_axis": "Probability",
                                "cells": [
                                    {"title": "Low-Low", "body": "Monitor routinely"},
                                    {"title": "Low-High", "body": "Prepare response"},
                                    {"title": "High-Low", "body": "Assign owner"},
                                    {"title": "High-High", "body": "Escalate now"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "matrix_grid")
        self.assertEqual(slide.x_axis, "Impact")
        self.assertEqual(slide.y_axis, "Probability")

    def test_compile_stats_block_to_dashboard_layout(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "KPI Overview",
                        "intent": "analysis",
                        "key_message": "Stabilize delivery while improving throughput.",
                        "blocks": [
                            {
                                "kind": "stats",
                                "heading": "Core Metrics",
                                "metrics": [
                                    {"label": "OTD", "value": "95%", "note": "Above target"},
                                    {"label": "Yield", "value": "98%", "note": "Stable month-on-month"},
                                    {"label": "Inventory", "value": "-12%", "note": "Healthy reduction"},
                                ],
                            },
                            {"kind": "bullets", "items": ["Focus on OTD stability", "Keep defect closure within weekly cadence"]},
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "stats_dashboard")
        self.assertEqual(len(slide.metrics), 3)
        self.assertGreaterEqual(len(slide.insights), 2)

    def test_compile_cards_block_to_cards_grid_layout(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Capability Map",
                        "intent": "framework",
                        "blocks": [
                            {
                                "kind": "cards",
                                "heading": "Three Capability Themes",
                                "cards": [
                                    {"title": "Plan", "body": "Align scope and governance"},
                                    {"title": "Build", "body": "Deliver reusable workflows"},
                                    {"title": "Operate", "body": "Close the improvement loop"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.layout, "cards_grid")
        self.assertEqual(len(slide.cards), 3)

    def test_compile_deck_diversifies_adjacent_generic_content_layouts(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Context",
                        "intent": "narrative",
                        "blocks": [{"kind": "bullets", "items": ["Set context", "Clarify scope", "Align constraints"]}],
                    },
                    {
                        "slide_id": "s2",
                        "title": "Actions",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "bullets",
                                "heading": "Actions",
                                "items": ["Assess baseline", "Design workflow", "Run pilot", "Scale rollout"],
                            }
                        ],
                    },
                ],
            }
        )

        first, second = validated.deck.slides
        self.assertEqual(first.layout, "title_content")
        self.assertEqual(second.layout, "two_columns")
        self.assertEqual(second.left.heading, "Actions")

    def test_compile_deck_preserves_strong_adjacent_semantic_layouts(self):
        validated = compile_semantic_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "title": "Risk A",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "matrix",
                                "cells": [
                                    {"title": "Low-Low", "body": "Monitor"},
                                    {"title": "High-High", "body": "Escalate"},
                                ],
                            }
                        ],
                    },
                    {
                        "slide_id": "s2",
                        "title": "Risk B",
                        "intent": "analysis",
                        "blocks": [
                            {
                                "kind": "matrix",
                                "cells": [
                                    {"title": "Low-High", "body": "Prepare"},
                                    {"title": "High-Low", "body": "Assign"},
                                ],
                            }
                        ],
                    },
                ],
            }
        )

        self.assertEqual([slide.layout for slide in validated.deck.slides], ["matrix_grid", "matrix_grid"])

if __name__ == "__main__":
    unittest.main()

