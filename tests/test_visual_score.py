import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt.models import BodyPageSpec, DeckSpec
from tools.sie_autoppt.visual_score import score_visual_draft
from tools.sie_autoppt.visual_spec import VisualComponent, VisualLayout, VisualSpec


def _good_spec() -> VisualSpec:
    return VisualSpec(
        slide_id="why_sie_choice",
        layout=VisualLayout(type="sales_proof"),
        components=[
            VisualComponent(type="headline", text="为什么选择 SiE 赛意"),
            VisualComponent(type="hero_claim", text="更低风险的追溯合规落地路径"),
            VisualComponent(type="proof_card", label="认证经验", value="TUV / SGS", detail="熟悉第三方审核关注点"),
            VisualComponent(type="value_band", text="少走弯路，降低试错"),
        ],
    )


class VisualScoreTests(unittest.TestCase):
    def test_good_sample_scores_at_least_85(self):
        html = (
            '<section class="slide"></section>'
            "<style>.slide{overflow: hidden;} .slide-body{left:72px;right:72px;top:108px;bottom:54px;} .x{font-size:16px; color:#111111;} .y{color:#222222;}</style>"
        )
        score = score_visual_draft(_good_spec(), html)
        self.assertGreaterEqual(score.score, 85)
        self.assertEqual(score.level, "pass")

    def test_missing_headline_lowers_score(self):
        spec = VisualSpec(
            slide_id="x",
            layout=VisualLayout(type="sales_proof"),
            components=[VisualComponent(type="hero_claim", text="claim")],
        )
        score = score_visual_draft(spec, '<section class="slide"></section>')
        self.assertLess(score.score, 85)

    def test_external_asset_lowers_score(self):
        score = score_visual_draft(_good_spec(), '<section class="slide"><img src="https://x.com/a.png"></section>')
        self.assertLess(score.score, 85)

    def test_scroll_risk_lowers_score(self):
        html = '<section class="slide"></section><style>.slide{overflow:auto;}</style>'
        score = score_visual_draft(_good_spec(), html)
        self.assertLess(score.score, 85)

    def test_too_small_font_lowers_score(self):
        baseline_html = (
            '<section class="slide"></section>'
            "<style>.slide{overflow: hidden;} .slide-body{left:72px;right:72px;top:108px;bottom:54px;} .x{font-size:16px;}</style>"
        )
        html = (
            '<section class="slide"></section>'
            "<style>.slide{overflow: hidden;} .x{font-size:10px;} .slide-body{left:72px;right:72px;top:108px;bottom:54px;}</style>"
        )
        baseline = score_visual_draft(_good_spec(), baseline_html)
        score = score_visual_draft(_good_spec(), html)
        self.assertLess(score.score, baseline.score)

    def test_safe_area_violation_lowers_score(self):
        baseline_html = (
            '<section class="slide"></section>'
            "<style>.slide{overflow: hidden;} .slide-body{left:72px;right:72px;top:108px;bottom:54px;} .x{font-size:16px;}</style>"
        )
        html = (
            '<section class="slide"></section>'
            "<style>.slide{overflow: hidden;} .slide-body{left:10px;right:10px;top:20px;bottom:10px;}</style>"
        )
        baseline = score_visual_draft(_good_spec(), baseline_html)
        score = score_visual_draft(_good_spec(), html)
        self.assertLess(score.score, baseline.score)

    def test_rule_config_override_changes_threshold_level(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "visual_rules.toml"
            rules_path.write_text(
                "\n".join(
                    [
                        "[scoring]",
                        "pass_threshold = 101",
                        "pass_with_notes_threshold = 80",
                        "auto_revise_threshold = 80",
                        "",
                        "[limits]",
                        "max_cards = 8",
                        "max_detail_chars = 90",
                        "min_font_px = 12",
                        "max_colors = 8",
                        "",
                        "[penalties]",
                        "missing_headline = 20",
                        "missing_claim = 15",
                        "too_many_cards = 20",
                        "detail_too_long = 8",
                        "unsupported_component = 20",
                        "missing_slide_root = 25",
                        "missing_overflow_hidden = 12",
                        "external_assets = 20",
                        "unknown_layout = 20",
                        "missing_screenshot = 8",
                        "too_small_font = 10",
                        "too_many_colors = 8",
                        "safe_area_violation = 12",
                        "safe_area_uncheckable = 6",
                    ]
                ),
                encoding="utf-8",
            )
            html = (
                '<section class="slide"></section>'
                "<style>.slide{overflow: hidden;} .slide-body{left:72px;right:72px;top:108px;bottom:54px;} .x{font-size:16px;}</style>"
            )
            score = score_visual_draft(_good_spec(), html, rules_path=str(rules_path))
        self.assertEqual(score.level, "pass_with_notes")

    def test_too_many_cards_lowers_score(self):
        spec = VisualSpec(
            slide_id="x",
            layout=VisualLayout(type="sales_proof"),
            components=[VisualComponent(type="headline", text="h"), VisualComponent(type="hero_claim", text="c")]
            + [VisualComponent(type="proof_card", label=str(i), value="v") for i in range(9)],
        )
        score = score_visual_draft(spec, '<section class="slide"></section>')
        self.assertLess(score.score, 85)

    def test_visual_service_auto_iterates_once(self):
        from tools.sie_autoppt.visual_service import generate_visual_draft_artifacts

        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="为什么选择 SiE 赛意",
                    subtitle="更低风险路径",
                    bullets=["TUV / SGS", "96.5% 客户保有率"],
                    pattern_id="claim_breakdown",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with (
                patch("tools.sie_autoppt.visual_service.capture_html_screenshot") as screenshot_mock,
                patch(
                    "tools.sie_autoppt.visual_service.review_visual_draft_with_ai",
                    side_effect=[
                        {
                            "score": 72,
                            "decision": "revise",
                            "summary": "需要调整",
                            "strengths": [],
                            "issues": ["焦点分散"],
                            "fixes": ["Move the main claim higher and increase contrast."],
                        },
                        {
                            "score": 82,
                            "decision": "pass_with_notes",
                            "summary": "可用",
                            "strengths": ["主张清晰"],
                            "issues": [],
                            "fixes": [],
                        },
                    ],
                ),
                patch(
                    "tools.sie_autoppt.visual_service.score_visual_draft",
                    side_effect=[
                        type("RuleScore", (), {"score": 70, "level": "revise", "issues": []})(),
                        type("RuleScore", (), {"score": 82, "level": "pass_with_notes", "issues": []})(),
                    ],
                ),
            ):
                screenshot_mock.side_effect = lambda **kwargs: kwargs["screenshot_path"].write_bytes(b"png")
                artifacts = generate_visual_draft_artifacts(
                    deck_spec=deck,
                    output_dir=output_dir,
                    output_name="why_sie_choice",
                    model="test-model",
                    with_ai_review=True,
                )

            self.assertEqual(artifacts.rule_score["score"], 82)
            self.assertTrue((output_dir / "why_sie_choice.preview.html").exists())
            self.assertTrue((output_dir / "why_sie_choice.preview.png").exists())
            self.assertTrue((output_dir / "why_sie_choice.round2.preview.html").exists())

    def test_visual_service_without_ai_review_does_not_call_model(self):
        from tools.sie_autoppt.visual_service import generate_visual_draft_artifacts

        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="为什么选择 SiE 赛意",
                    subtitle="更低风险路径",
                    bullets=["TUV / SGS"],
                    pattern_id="claim_breakdown",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with (
                patch("tools.sie_autoppt.visual_service.capture_html_screenshot") as screenshot_mock,
                patch("tools.sie_autoppt.visual_service.review_visual_draft_with_ai") as ai_mock,
                patch(
                    "tools.sie_autoppt.visual_service.score_visual_draft",
                    return_value=type("RuleScore", (), {"score": 86, "level": "pass", "issues": []})(),
                ),
            ):
                screenshot_mock.side_effect = lambda **kwargs: kwargs["screenshot_path"].write_bytes(b"png")
                artifacts = generate_visual_draft_artifacts(
                    deck_spec=deck,
                    output_dir=output_dir,
                    output_name="why_sie_choice",
                    with_ai_review=False,
                )

            ai_mock.assert_not_called()
            self.assertEqual(artifacts.ai_review["status"], "skipped")

    def test_visual_service_uses_configured_auto_revise_threshold(self):
        from tools.sie_autoppt.visual_service import generate_visual_draft_artifacts

        deck = DeckSpec(
            cover_title="demo",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="为什么选择 SiE 赛意",
                    subtitle="更低风险路径",
                    bullets=["TUV / SGS"],
                    pattern_id="claim_breakdown",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            rules_path = output_dir / "visual_rules.toml"
            rules_path.write_text(
                "\n".join(
                    [
                        "[scoring]",
                        "pass_threshold = 90",
                        "pass_with_notes_threshold = 80",
                        "auto_revise_threshold = 85",
                        "",
                        "[limits]",
                        "max_cards = 8",
                        "max_detail_chars = 90",
                        "min_font_px = 12",
                        "max_colors = 8",
                        "",
                        "[penalties]",
                        "missing_headline = 20",
                        "missing_claim = 15",
                        "too_many_cards = 20",
                        "detail_too_long = 8",
                        "unsupported_component = 20",
                        "missing_slide_root = 25",
                        "missing_overflow_hidden = 12",
                        "external_assets = 20",
                        "unknown_layout = 20",
                        "missing_screenshot = 8",
                        "too_small_font = 10",
                        "too_many_colors = 8",
                        "safe_area_violation = 12",
                        "safe_area_uncheckable = 6",
                    ]
                ),
                encoding="utf-8",
            )
            with (
                patch("tools.sie_autoppt.visual_service.capture_html_screenshot") as screenshot_mock,
                patch(
                    "tools.sie_autoppt.visual_service.score_visual_draft",
                    return_value=type("RuleScore", (), {"score": 80, "level": "pass_with_notes", "issues": []})(),
                ),
            ):
                screenshot_mock.side_effect = lambda **kwargs: kwargs["screenshot_path"].write_bytes(b"png")
                with self.assertRaises(RuntimeError):
                    generate_visual_draft_artifacts(
                        deck_spec=deck,
                        output_dir=output_dir,
                        output_name="why_sie_choice",
                        with_ai_review=False,
                        visual_rules_path=str(rules_path),
                    )


if __name__ == "__main__":
    unittest.main()
