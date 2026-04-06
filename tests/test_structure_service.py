import unittest
from unittest.mock import patch

from tools.sie_autoppt.structure_service import (
    StructureGenerationRequest,
    build_structure_schema,
    generate_structure_with_ai,
    resolve_structure_bounds,
    validate_structure_payload,
)


class _FakeClient:
    def __init__(self, _config, responses):
        self._responses = list(responses)

    def create_structured_json(self, developer_prompt, user_prompt, schema_name, schema):
        return self._responses.pop(0)


class StructureServiceTests(unittest.TestCase):
    def test_build_structure_schema_uses_requested_bounds(self):
        schema = build_structure_schema(resolve_structure_bounds(StructureGenerationRequest(topic="AI", sections=4)))

        self.assertEqual(schema["properties"]["sections"]["minItems"], 4)
        self.assertEqual(schema["properties"]["sections"]["maxItems"], 4)

    def test_validate_structure_payload_rejects_duplicate_and_weak_titles(self):
        result = validate_structure_payload(
            {
                "core_message": "AI 正在进入规模化落地阶段",
                "structure_type": "industry_analysis",
                "sections": [
                    {
                        "title": "未来可期",
                        "key_message": "非常重要",
                        "arguments": [{"point": "A", "evidence": ""}, {"point": "B", "evidence": ""}],
                    },
                    {
                        "title": "未来可期",
                        "key_message": "重复",
                        "arguments": [{"point": "C", "evidence": ""}, {"point": "D", "evidence": ""}],
                    },
                    {
                        "title": "第三部分",
                        "key_message": "补充说明",
                        "arguments": [{"point": "E", "evidence": ""}, {"point": "F", "evidence": ""}],
                    },
                ],
            }
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicated" in issue for issue in result.issues))
        self.assertTrue(any("weak phrasing" in issue for issue in result.issues))

    def test_generate_structure_with_ai_retries_until_validation_passes(self):
        invalid = {
            "core_message": "AI 正在进入规模化落地阶段",
            "structure_type": "industry_analysis",
            "sections": [
                {"title": "过短", "key_message": "缺参数", "arguments": [{"point": "A", "evidence": ""}]},
                {"title": "第二部分", "key_message": "补充", "arguments": [{"point": "B", "evidence": ""}]},
                {"title": "第三部分", "key_message": "补充", "arguments": [{"point": "C", "evidence": ""}]},
            ],
        }
        valid = {
            "core_message": "AI 正从技术突破进入产业落地阶段",
            "structure_type": "industry_analysis",
            "sections": [
                {
                    "title": "模型能力提升正在降低应用试错成本",
                    "key_message": "能力和成本改善让企业更容易进入试点",
                    "arguments": [
                        {"point": "基础模型效果持续增强", "evidence": ""},
                        {"point": "部署门槛不断降低", "evidence": ""},
                    ],
                },
                {
                    "title": "场景落地正在从单点提效转向流程重构",
                    "key_message": "企业开始把 AI 嵌入完整业务流程",
                    "arguments": [
                        {"point": "从问答走向工作流协同", "evidence": ""},
                        {"point": "从工具试用走向岗位重构", "evidence": ""},
                    ],
                },
                {
                    "title": "竞争优势将更多来自组织执行而非模型本身",
                    "key_message": "数据、流程和治理决定最终收益",
                    "arguments": [
                        {"point": "治理能力决定落地速度", "evidence": ""},
                        {"point": "数据质量决定输出稳定性", "evidence": ""},
                    ],
                },
            ],
        }

        with patch("tools.sie_autoppt.structure_service.load_openai_responses_config", return_value=object()):
            with patch(
                "tools.sie_autoppt.structure_service.OpenAIResponsesClient",
                side_effect=lambda config: _FakeClient(config, [invalid, valid]),
            ):
                result = generate_structure_with_ai(
                    StructureGenerationRequest(topic="做一个 AI 行业趋势汇报"),
                    model="test-model",
                )

        self.assertEqual(result.attempts_used, 2)
        self.assertEqual(result.structure.core_message, "AI 正从技术突破进入产业落地阶段")
        self.assertEqual(len(result.structure.sections), 3)
