import unittest

from tools.sie_autoppt.language_policy import (
    format_language_constraints,
    get_language_policy,
    normalize_language_code,
)


class LanguagePolicyTests(unittest.TestCase):
    def test_normalize_language_code_supports_aliases(self):
        self.assertEqual(normalize_language_code("zh"), "zh-CN")
        self.assertEqual(normalize_language_code("en"), "en-US")
        self.assertEqual(normalize_language_code("en_us"), "en-US")

    def test_get_language_policy_falls_back_to_zh_cn(self):
        policy = get_language_policy("unknown-language")
        self.assertEqual(policy.code, "zh-CN")

    def test_format_language_constraints_returns_bullet_lines(self):
        policy = get_language_policy("en-US")
        constraint_block = format_language_constraints(policy)
        self.assertIn("All user-facing text must be in English.", constraint_block)
        self.assertIn("- ", constraint_block)
