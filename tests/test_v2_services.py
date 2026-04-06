import unittest

from tools.sie_autoppt.v2.schema import OutlineDocument
from tools.sie_autoppt.v2.services import (
    DeckGenerationRequest,
    OutlineGenerationRequest,
    build_deck_prompts,
    build_outline_prompts,
    resolve_slide_bounds,
)


class V2ServiceTests(unittest.TestCase):
    def test_resolve_slide_bounds_supports_exact_and_range(self):
        self.assertEqual(
            resolve_slide_bounds(OutlineGenerationRequest(topic="AI", exact_slides=8)),
            (8, 8),
        )
        self.assertEqual(
            resolve_slide_bounds(OutlineGenerationRequest(topic="AI", min_slides=6, max_slides=9)),
            (6, 9),
        )

    def test_prompt_builders_include_core_constraints(self):
        outline_request = OutlineGenerationRequest(topic="AI strategy", min_slides=6, max_slides=8)
        developer_prompt, user_prompt = build_outline_prompts(outline_request)
        self.assertIn("Return 6-8 pages.", developer_prompt)
        self.assertIn("AI strategy", user_prompt)

        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain key issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present the roadmap."},
                ]
            }
        )
        deck_request = DeckGenerationRequest(topic="AI strategy", outline=outline)
        developer_prompt, user_prompt = build_deck_prompts(deck_request)
        self.assertIn("section_break", developer_prompt)
        self.assertIn('"page_no": 1', user_prompt)
