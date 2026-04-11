import unittest

from tools.sie_autoppt.visual_html_renderer import render_visual_spec_to_html
from tools.sie_autoppt.visual_spec import (
    VisualComponent,
    VisualLayout,
    VisualSpec,
)


def _build_spec(layout_type: str) -> VisualSpec:
    return VisualSpec(
        slide_id=f"slide_{layout_type}",
        layout=VisualLayout(type=layout_type),
        components=[
            VisualComponent(type="headline", text="为什么选择 SiE 赛意"),
            VisualComponent(type="subheadline", text="更低风险的追溯合规路径"),
            VisualComponent(type="hero_claim", text="核心主张"),
            VisualComponent(type="proof_card", label="认证经验", value="TUV / SGS", detail="熟悉第三方审核"),
            VisualComponent(type="value_band", text="少走弯路、降低试错"),
        ],
    )


class VisualHtmlRendererTests(unittest.TestCase):
    def test_single_slide_no_remote_assets(self):
        html = render_visual_spec_to_html(_build_spec("sales_proof"))
        self.assertEqual(html.count('class="slide"'), 1)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn("overflow: hidden", html)

    def test_contains_required_data_roles(self):
        html = render_visual_spec_to_html(_build_spec("risk_to_value"))
        self.assertIn('data-role="title"', html)
        self.assertIn('data-role="main-claim"', html)
        self.assertIn('data-role="proof-card"', html)
        self.assertIn("为什么选择 SiE 赛意", html)

    def test_supports_three_layout_shells(self):
        for layout_type in ("sales_proof", "risk_to_value", "executive_summary"):
            html = render_visual_spec_to_html(_build_spec(layout_type))
            self.assertIn(f'data-layout="{layout_type}"', html)


if __name__ == "__main__":
    unittest.main()
