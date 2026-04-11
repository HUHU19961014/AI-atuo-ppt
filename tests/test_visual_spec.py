import unittest

from tools.sie_autoppt.deck_spec_io import deck_spec_to_dict
from tools.sie_autoppt.models import BodyPageSpec, DeckSpec
from tools.sie_autoppt.visual_service import build_visual_spec_from_deck_spec
from tools.sie_autoppt.visual_spec import (
    VisualComponent,
    VisualLayout,
    VisualSpec,
)


class VisualSpecTests(unittest.TestCase):
    def test_valid_sample_parses(self):
        payload = {
            "schema_version": "0.1",
            "slide_id": "why_sie_choice",
            "layout": {"type": "sales_proof"},
            "components": [
                {"type": "headline", "text": "Why SiE"},
                {"type": "proof_card", "label": "Cert", "value": "TUV / SGS"},
            ],
        }
        spec = VisualSpec.from_dict(payload)
        self.assertEqual(spec.slide_id, "why_sie_choice")
        self.assertEqual(spec.canvas.width, 1280)
        self.assertEqual(spec.canvas.height, 720)
        self.assertEqual(spec.layout.type, "sales_proof")

    def test_empty_slide_id_fails(self):
        with self.assertRaises(ValueError):
            VisualSpec(
                slide_id="",
                layout=VisualLayout(type="sales_proof"),
                components=[VisualComponent(type="headline", text="ok")],
            )

    def test_unknown_component_type_fails(self):
        with self.assertRaises(ValueError):
            VisualComponent(type="unknown_card", text="x")

    def test_unknown_layout_type_fails(self):
        with self.assertRaises(ValueError):
            VisualLayout(type="mystery")

    def test_mapper_preserves_key_values_and_chinese_risk_routing(self):
        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="为什么选择 SiE 赛意",
                    subtitle="更低风险的追溯合规路径",
                    bullets=["存在风险敞口", "96.5% 客户保有率"],
                    pattern_id="general_business",
                    payload={
                        "claims": [
                            {"label": "认证经验", "value": "TUV / SGS", "detail": "熟悉审核关注点"},
                        ],
                        "headline": "让追溯与合规更快落地",
                    },
                )
            ],
        )

        spec = build_visual_spec_from_deck_spec(deck, page_index=0, layout_hint="auto")
        serialized = spec.to_dict()
        as_text = str(serialized)
        self.assertEqual(spec.layout.type, "risk_to_value")
        self.assertIn("TUV / SGS", as_text)
        self.assertIn("96.5% 客户保有率", as_text)
        self.assertIn("更低风险的追溯合规路径", as_text)
        self.assertIn("risk_card", as_text)

    def test_mapper_uses_payload_headline_as_subheadline_when_subtitle_missing(self):
        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="为什么选择 SiE 赛意",
                    subtitle="",
                    bullets=["主张"],
                    pattern_id="general_business",
                    payload={"headline": "让追溯与合规更快落地"},
                )
            ],
        )
        spec = build_visual_spec_from_deck_spec(deck, page_index=0, layout_hint="auto")
        text_dump = str(spec.to_dict())
        self.assertIn("让追溯与合规更快落地", text_dump)

    def test_mapper_does_not_mutate_input_deck_spec(self):
        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="A",
                    subtitle="B",
                    bullets=["C", "D"],
                    pattern_id="claim_breakdown",
                    payload={"headline": "H"},
                )
            ],
        )
        before = deck_spec_to_dict(deck)
        _ = build_visual_spec_from_deck_spec(deck, page_index=0, layout_hint="auto")
        after = deck_spec_to_dict(deck)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
