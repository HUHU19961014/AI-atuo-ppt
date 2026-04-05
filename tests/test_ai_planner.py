import json
import sys
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.planning.ai_planner import (
    AiPlanningRequest,
    build_ai_outline_schema,
    build_external_planner_payload,
    build_ai_planning_prompts,
    build_deck_spec_from_ai_outline,
    plan_deck_spec_with_ai,
    resolve_external_planner_command,
)


class AiPlannerTests(unittest.TestCase):
    def test_outline_schema_matches_requested_page_count(self):
        schema = build_ai_outline_schema(3)

        self.assertEqual(schema["properties"]["body_pages"]["minItems"], 3)
        self.assertEqual(schema["properties"]["body_pages"]["maxItems"], 3)
        self.assertIn("pattern_id", schema["properties"]["body_pages"]["items"]["properties"])

    def test_build_deck_spec_from_ai_outline_normalizes_patterns(self):
        deck = build_deck_spec_from_ai_outline(
            {
                "cover_title": "AI 自动化转型方案",
                "body_pages": [
                    {
                        "title": "现状与痛点",
                        "subtitle": "识别当前主要阻碍",
                        "bullets": ["流程割裂导致协同成本高", "数据口径不一致影响决策效率"],
                        "pattern_id": "pain_points",
                        "nav_title": "痛点",
                    },
                    {
                        "title": "目标架构",
                        "subtitle": "统一平台与能力中台",
                        "bullets": ["统一数据底座与集成层", "沉淀可复用业务能力模块"],
                        "pattern_id": "solution_architecture",
                        "nav_title": "架构",
                    },
                    {
                        "title": "实施路径",
                        "subtitle": "分阶段推进落地",
                        "bullets": ["先打通关键业务链路", "再扩展到跨部门协同场景"],
                        "pattern_id": "implementation_plan",
                        "nav_title": "路径",
                    },
                ],
            },
            chapters=3,
        )

        self.assertEqual(deck.cover_title, "AI 自动化转型方案")
        self.assertEqual(
            [page.pattern_id for page in deck.body_pages],
            ["general_business", "solution_architecture", "process_flow"],
        )
        self.assertEqual([page.page_key for page in deck.body_pages], ["ai_page_01", "ai_page_02", "ai_page_03"])

    def test_build_ai_planning_prompts_embed_topic_and_brief(self):
        developer_prompt, user_prompt = build_ai_planning_prompts(
            AiPlanningRequest(
                topic="制造业 ERP 智能化升级",
                chapters=3,
                audience="CIO / 业务负责人",
                brief="现有系统分散，主数据治理薄弱。",
            )
        )

        self.assertIn("Return exactly 3 body pages", developer_prompt)
        self.assertIn("制造业 ERP 智能化升级", user_prompt)
        self.assertIn("现有系统分散", user_prompt)

    def test_build_external_planner_payload_contains_schema_and_prompts(self):
        request = AiPlanningRequest(topic="测试主题", chapters=2, audience="管理层", brief="补充材料")
        developer_prompt, user_prompt = build_ai_planning_prompts(request)

        payload = build_external_planner_payload(request, developer_prompt, user_prompt)

        self.assertEqual(payload["request"]["topic"], "测试主题")
        self.assertEqual(payload["outline_schema"]["properties"]["body_pages"]["minItems"], 2)
        self.assertIn("Return exactly 2 body pages", payload["developer_prompt"])

    def test_plan_deck_spec_with_ai_supports_external_command(self):
        outline = {
            "cover_title": "外部规划器验证",
            "body_pages": [
                {
                    "title": "第一页",
                    "subtitle": "摘要",
                    "bullets": ["要点一", "要点二"],
                    "pattern_id": "general_business",
                    "nav_title": "第一页",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "external_planner.py"
            script_path.write_text(
                "import json, sys\n"
                "json.load(sys.stdin)\n"
                f"print({json.dumps(json.dumps(outline, ensure_ascii=False))})\n",
                encoding="utf-8",
            )
            command = f'{sys.executable} "{script_path}"'

            deck = plan_deck_spec_with_ai(
                AiPlanningRequest(topic="外部命令测试", chapters=1),
                planner_command=command,
            )

        self.assertEqual(deck.cover_title, "外部规划器验证")
        self.assertEqual(deck.body_pages[0].title, "第一页")

    def test_resolve_external_planner_command_prefers_explicit_value(self):
        self.assertEqual(resolve_external_planner_command("echo test"), "echo test")
