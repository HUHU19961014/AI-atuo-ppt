import unittest

from tools.sie_autoppt.v2.semantic_compiler import compile_semantic_deck_payload


class ContentDensitySplitTests(unittest.TestCase):
    def test_dense_title_content_is_split_into_multiple_pages_with_4_to_6_items(self):
        items = [f"要点{i}" for i in range(1, 11)]
        payload = {
            "meta": {"title": "Test Deck", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "核心建议",
                    "intent": "analysis",
                    "blocks": [{"kind": "bullets", "items": items}],
                }
            ],
        }

        deck = compile_semantic_deck_payload(payload).deck
        self.assertGreaterEqual(len(deck.slides), 2)
        for slide in deck.slides:
            self.assertEqual(slide.layout, "title_content")
            self.assertGreaterEqual(len(slide.content), 4)
            self.assertLessEqual(len(slide.content), 6)

