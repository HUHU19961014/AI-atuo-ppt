import unittest

from tools.sie_autoppt.config import INPUT_DIR
from tools.sie_autoppt.pipeline import plan_deck_from_html
from tools.sie_autoppt.planning.deck_planner import (
    build_deck_spec_from_html,
    build_directory_lines,
    clamp_requested_chapters,
)


class DeckPlannerTests(unittest.TestCase):
    def test_clamp_requested_chapters_respects_bounds(self):
        self.assertEqual(clamp_requested_chapters(0, 3), 1)
        self.assertEqual(clamp_requested_chapters(2, 3), 2)
        self.assertEqual(clamp_requested_chapters(99, 3), 3)
        self.assertEqual(clamp_requested_chapters(3, 2), 2)

    def test_standard_html_builds_three_default_pages(self):
        html = (INPUT_DIR / "uat_plan_sample.html").read_text(encoding="utf-8")

        deck = build_deck_spec_from_html(html, chapters=3)

        self.assertEqual(len(deck.body_pages), 3)
        self.assertEqual([page.page_key for page in deck.body_pages], ["overview", "scope", "focus"])
        self.assertEqual(len(build_directory_lines(deck.body_pages)), 5)

    def test_card_analysis_html_uses_reference_styles(self):
        html = (INPUT_DIR / "ai_pythonpptx_strategy.html").read_text(encoding="utf-8")

        deck = build_deck_spec_from_html(html, chapters=3)

        self.assertEqual(
            [page.reference_style_id for page in deck.body_pages],
            ["comparison_upgrade", "capability_ring", "five_phase_path"],
        )
        self.assertEqual(
            [page.pattern_id for page in deck.body_pages],
            ["comparison_upgrade", "capability_ring", "five_phase_path"],
        )

    def test_pipeline_returns_matching_pattern_ids_and_directory_lines(self):
        plan = plan_deck_from_html(INPUT_DIR / "architecture_program_sample.html", chapters=3)

        self.assertEqual(len(plan.pattern_ids), len(plan.deck.body_pages))
        self.assertEqual(plan.pattern_ids, [page.pattern_id for page in plan.deck.body_pages])
        self.assertEqual(len(plan.chapter_lines), 5)
        self.assertEqual(plan.chapter_lines[-1], "Q&A")
