import unittest

from tools.sie_autoppt.patterns import (
    infer_pattern,
    infer_pattern_details,
)


class PatternInferenceTests(unittest.TestCase):
    def test_infer_pattern_supports_english_architecture_terms(self):
        pattern_id = infer_pattern(
            "ERP Architecture Blueprint",
            ["Application landscape", "Core platform modules", "Integration system design"],
        )

        self.assertEqual(pattern_id, "solution_architecture")

    def test_infer_pattern_handles_governance_typos(self):
        pattern_id = infer_pattern(
            "Program governence and ownership",
            ["Role mapping", "Team responsibilities", "Operating model"],
        )

        self.assertEqual(pattern_id, "org_governance")

    def test_infer_pattern_recognizes_process_flow_aliases(self):
        pattern_id = infer_pattern(
            "Workflow journey",
            ["Stage alignment", "Execution flow", "End-to-end steps"],
        )

        self.assertEqual(pattern_id, "process_flow")

    def test_infer_pattern_recognizes_roadmap_timeline(self):
        pattern_id = infer_pattern(
            "年度路线图与里程碑",
            ["Q1: 完成诊断", "Q2: 建设平台", "Q3: 试点上线"],
        )

        self.assertEqual(pattern_id, "roadmap_timeline")

    def test_infer_pattern_recognizes_kpi_dashboard(self):
        pattern_id = infer_pattern(
            "经营指标仪表盘",
            ["收入增速: 18%", "毛利率: 32%", "重点项目: 12 个"],
        )

        self.assertEqual(pattern_id, "kpi_dashboard")

    def test_infer_pattern_recognizes_risk_matrix(self):
        pattern_id = infer_pattern(
            "风险矩阵评估",
            ["汇率波动", "政策不确定性", "执行延期风险"],
        )

        self.assertEqual(pattern_id, "risk_matrix")

    def test_infer_pattern_recognizes_claim_breakdown(self):
        pattern_id = infer_pattern(
            "索赔金额拆解",
            ["电费欠款: $2.1B", "违约利息: $1.3B", "汇率损失: $0.8B"],
        )

        self.assertEqual(pattern_id, "claim_breakdown")

    def test_infer_pattern_details_marks_low_confidence_generic_content(self):
        result = infer_pattern_details(
            "Executive overview",
            ["Strategic priorities", "Cross-functional collaboration"],
        )

        self.assertEqual(result.pattern_id, "general_business")
        self.assertTrue(result.low_confidence)
        self.assertFalse(result.used_ai_assist)

    def test_infer_pattern_details_can_use_ai_assist_resolver(self):
        result = infer_pattern_details(
            "Executive overview",
            ["Strategic priorities", "Cross-functional collaboration"],
            enable_ai_assist=True,
            ai_pattern_resolver=lambda title, bullets, candidates: "process_flow",
        )

        self.assertEqual(result.pattern_id, "process_flow")
        self.assertTrue(result.low_confidence)
        self.assertTrue(result.used_ai_assist)
