import unittest

from tools.sie_autoppt.patterns import infer_pattern


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
