import unittest

from tools.sie_autoppt.v2.schema import (
    OutlineDocument,
    collect_deck_warnings,
    validate_deck_payload,
)


class V2SchemaTests(unittest.TestCase):
    def test_outline_document_requires_contiguous_page_numbers(self):
        with self.assertRaises(ValueError):
            OutlineDocument.model_validate(
                {
                    "pages": [
                        {"page_no": 1, "title": "Page 1", "goal": "Explain the context."},
                        {"page_no": 3, "title": "Page 3", "goal": "Skip a page number."},
                    ]
                }
            )

    def test_validate_deck_payload_normalizes_defaults_and_collects_warnings(self):
        validated = validate_deck_payload(
            {
                "slides": [
                    {
                        "layout": "title_content",
                        "title": "A very long page title that should trigger a warning",
                        "content": [
                            "Point one is concise.",
                            "Point two is concise.",
                            "Point three is concise.",
                            "Point four is concise.",
                            "Point five is concise.",
                            "Point six is concise.",
                            "Point seven is concise.",
                        ],
                    }
                ]
            },
            default_title="Sample Deck",
        )

        self.assertEqual(validated.deck.meta.title, "Sample Deck")
        self.assertEqual(validated.deck.slides[0].slide_id, "s1")
        self.assertTrue(any("longer than 24 characters" in item for item in validated.warnings))
        self.assertTrue(any("more than 6 bullet items" in item for item in validated.warnings))
        self.assertEqual(list(validated.warnings), collect_deck_warnings(validated.deck))
