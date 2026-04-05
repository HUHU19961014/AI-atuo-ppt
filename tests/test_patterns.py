import unittest

from tools.sie_autoppt.patterns import infer_pattern, infer_pattern_details


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
