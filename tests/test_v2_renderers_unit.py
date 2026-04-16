import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from tools.sie_autoppt.v2.renderers.cards_grid import render_cards_grid
from tools.sie_autoppt.v2.renderers.common import RenderContext
from tools.sie_autoppt.v2.renderers.matrix_grid import render_matrix_grid
from tools.sie_autoppt.v2.renderers.section_break import render_section_break
from tools.sie_autoppt.v2.renderers.stats_dashboard import render_stats_dashboard
from tools.sie_autoppt.v2.renderers.timeline import render_timeline
from tools.sie_autoppt.v2.renderers.title_content import render_title_content
from tools.sie_autoppt.v2.renderers.title_image import render_title_image
from tools.sie_autoppt.v2.renderers.title_only import render_title_only
from tools.sie_autoppt.v2.renderers.two_columns import render_two_columns
from tools.sie_autoppt.v2.schema import (
    CardsGridSlide,
    MatrixGridSlide,
    SectionBreakSlide,
    StatsDashboardSlide,
    TimelineSlide,
    TitleContentSlide,
    TitleImageSlide,
    TitleOnlySlide,
    TwoColumnsSlide,
)
from tools.sie_autoppt.v2.theme_loader import ThemeSpec


def _theme() -> ThemeSpec:
    return ThemeSpec.model_validate(
        {
            "theme_name": "unit-test-theme",
            "page": {"width": 13.333, "height": 7.5},
            "colors": {
                "primary": "#123456",
                "secondary": "#234567",
                "text_main": "#345678",
                "text_sub": "#456789",
                "bg": "#FFFFFF",
                "card_bg": "#F4F6F8",
                "line": "#D0D7DE",
            },
            "fonts": {"title": "Arial", "body": "Arial", "fallback": "Arial"},
            "font_sizes": {"title": 28, "subtitle": 18, "body": 14, "small": 12},
            "spacing": {
                "page_margin_left": 0.5,
                "page_margin_right": 0.5,
                "page_margin_top": 0.5,
                "page_margin_bottom": 0.5,
                "block_gap": 0.2,
            },
            "layouts": {},
        }
    )


class V2RendererUnitTests(unittest.TestCase):
    def _ctx(self) -> RenderContext:
        return RenderContext(
            prs=object(),
            theme=_theme(),
            log=Mock(),
            slide_number=1,
            total_slides=3,
        )

    def test_render_two_columns_uses_comparison_table_path_when_balanced(self):
        slide_data = TwoColumnsSlide.model_validate(
            {
                "slide_id": "s1",
                "layout": "two_columns",
                "title": "Comparison",
                "left": {"heading": "Current", "items": ["a", "b"]},
                "right": {"heading": "Target", "items": ["x", "y"]},
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.two_columns.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.should_render_comparison_table", return_value=True),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_comparison_table") as add_comparison_table,
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_card") as add_card,
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_page_number"),
        ):
            render_two_columns(self._ctx(), slide_data)

        add_comparison_table.assert_called_once()
        add_card.assert_not_called()

    def test_render_two_columns_applies_dynamic_geometry_for_unbalanced_content(self):
        slide_data = TwoColumnsSlide.model_validate(
            {
                "slide_id": "s1",
                "layout": "two_columns",
                "title": "Comparison",
                "left": {"heading": "Current", "items": ["a", "b", "c", "d", "e", "f"]},
                "right": {"heading": "Target", "items": ["x"]},
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.two_columns.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.should_render_comparison_table", return_value=False),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_comparison_table"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_card") as add_card,
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_page_number"),
        ):
            render_two_columns(self._ctx(), slide_data)

        self.assertEqual(add_card.call_count, 2)
        left_card_call = add_card.call_args_list[0]
        right_card_call = add_card.call_args_list[1]
        self.assertGreater(left_card_call.args[3], right_card_call.args[3])

    def test_render_two_columns_uses_style_variant_to_adjust_density(self):
        base_payload = {
            "slide_id": "s1",
            "layout": "two_columns",
            "title": "Comparison",
            "left": {"heading": "Current", "items": ["a", "b", "c"]},
            "right": {"heading": "Target", "items": ["x", "y", "z"]},
        }
        minimal_slide = TwoColumnsSlide.model_validate({**base_payload, "style_variant": "minimal"})
        decorative_slide = TwoColumnsSlide.model_validate({**base_payload, "style_variant": "decorative"})

        with (
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.two_columns.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.should_render_comparison_table", return_value=False),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_comparison_table"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_card") as add_card_minimal,
        ):
            render_two_columns(self._ctx(), minimal_slide)

        with (
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.two_columns.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.should_render_comparison_table", return_value=False),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_comparison_table"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.two_columns.add_card") as add_card_decorative,
        ):
            render_two_columns(self._ctx(), decorative_slide)

        minimal_left_width = add_card_minimal.call_args_list[0].args[3]
        decorative_left_width = add_card_decorative.call_args_list[0].args[3]
        self.assertGreater(decorative_left_width, minimal_left_width)

    def test_render_title_content_uses_bullets_when_not_timeline(self):
        slide_data = TitleContentSlide.model_validate(
            {
                "slide_id": "s1",
                "layout": "title_content",
                "title": "Content",
                "content": ["one", "two", "three"],
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_content.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_content.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_content.parse_timeline_items", return_value=None),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_bullet_list") as add_bullet_list,
            patch("tools.sie_autoppt.v2.renderers.title_content.add_timeline_flow") as add_timeline_flow,
            patch("tools.sie_autoppt.v2.renderers.title_content.add_page_number"),
        ):
            render_title_content(self._ctx(), slide_data)

        add_bullet_list.assert_called_once()
        add_timeline_flow.assert_not_called()

    def test_render_title_content_uses_timeline_when_parse_matches(self):
        slide_data = TitleContentSlide.model_validate(
            {
                "slide_id": "s2",
                "layout": "title_content",
                "title": "Roadmap",
                "content": ["Q1: Align", "Q2: Pilot"],
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_content.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_content.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_content.parse_timeline_items", return_value=[("Q1", "Align"), ("Q2", "Pilot")]),
            patch("tools.sie_autoppt.v2.renderers.title_content.add_bullet_list") as add_bullet_list,
            patch("tools.sie_autoppt.v2.renderers.title_content.add_timeline_flow") as add_timeline_flow,
            patch("tools.sie_autoppt.v2.renderers.title_content.add_page_number"),
        ):
            render_title_content(self._ctx(), slide_data)
        add_timeline_flow.assert_called_once()
        add_bullet_list.assert_not_called()

    def test_render_stats_dashboard_renders_insights_title(self):
        slide_data = StatsDashboardSlide.model_validate(
            {
                "slide_id": "s1",
                "layout": "stats_dashboard",
                "title": "Dashboard",
                "metrics": [
                    {"label": "OTD", "value": "95%", "note": "Stable"},
                    {"label": "Yield", "value": "98%", "note": "Improving"},
                ],
                "insights": ["Keep momentum"],
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_card"),
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_textbox") as add_textbox,
        ):
            render_stats_dashboard(self._ctx(), slide_data)
        self.assertGreaterEqual(add_textbox.call_count, 3)

    def test_render_stats_dashboard_adds_chart_when_numeric_metrics_available(self):
        slide_data = StatsDashboardSlide.model_validate(
            {
                "slide_id": "s2",
                "layout": "stats_dashboard",
                "title": "Dashboard",
                "metrics": [
                    {"label": "Revenue", "value": "120", "note": "Q1"},
                    {"label": "Margin", "value": "95", "note": "Q1"},
                    {"label": "Cost", "value": "80", "note": "Q1"},
                ],
                "insights": [],
            }
        )
        fake_slide = Mock()
        with tempfile.TemporaryDirectory() as temp_dir:
            chart_path = Path(temp_dir) / "chart.png"
            chart_path.write_bytes(b"png")
            with (
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_blank_slide", return_value=fake_slide),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.fill_background"),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_card"),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_bullet_list"),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_page_number"),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard.add_textbox"),
                patch("tools.sie_autoppt.v2.renderers.stats_dashboard._build_metrics_chart_image", return_value=chart_path),
            ):
                render_stats_dashboard(self._ctx(), slide_data)
        fake_slide.shapes.add_picture.assert_called()

    def test_render_title_image_uses_placeholder_when_local_image_missing(self):
        slide_data = TitleImageSlide.model_validate(
            {
                "slide_id": "s1",
                "layout": "title_image",
                "title": "Architecture",
                "content": ["point1", "point2"],
                "image": {"mode": "local_path", "path": "missing.png", "caption": "Diagram"},
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_image.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_image.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_local_image_or_placeholder", return_value=False)
            as add_local_image_or_placeholder,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_capability_map") as add_capability_map,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_architecture_placeholder") as add_architecture_placeholder,
        ):
            render_title_image(self._ctx(), slide_data)
        add_local_image_or_placeholder.assert_called_once()
        self.assertEqual(add_architecture_placeholder.call_count + add_capability_map.call_count, 0)

    def test_render_title_image_placeholder_architecture_branch(self):
        slide_data = TitleImageSlide.model_validate(
            {
                "slide_id": "s3",
                "layout": "title_image",
                "title": "Reference Architecture",
                "content": ["data", "model", "serving"],
                "image": {"mode": "placeholder", "caption": "架构图"},
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_image.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_image.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.title_image.classify_placeholder_visual", return_value="architecture"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_local_image_or_placeholder") as add_local_image_or_placeholder,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_capability_map") as add_capability_map,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_architecture_placeholder") as add_architecture_placeholder,
        ):
            render_title_image(self._ctx(), slide_data)
        add_architecture_placeholder.assert_called_once()
        add_capability_map.assert_not_called()
        add_local_image_or_placeholder.assert_not_called()

    def test_render_title_image_placeholder_map_branch(self):
        slide_data = TitleImageSlide.model_validate(
            {
                "slide_id": "s4",
                "layout": "title_image",
                "title": "Capability Map",
                "content": ["planning", "execution", "governance"],
                "image": {"mode": "placeholder", "caption": "能力地图"},
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_image.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_image.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_bullet_list"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.title_image.classify_placeholder_visual", return_value="map"),
            patch("tools.sie_autoppt.v2.renderers.title_image.add_local_image_or_placeholder") as add_local_image_or_placeholder,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_capability_map") as add_capability_map,
            patch("tools.sie_autoppt.v2.renderers.title_image.add_architecture_placeholder") as add_architecture_placeholder,
        ):
            render_title_image(self._ctx(), slide_data)
        add_capability_map.assert_called_once()
        add_architecture_placeholder.assert_not_called()
        add_local_image_or_placeholder.assert_not_called()

    def test_render_section_break_renders_subtitle(self):
        slide_data = SectionBreakSlide.model_validate(
            {
                "slide_id": "s5",
                "layout": "section_break",
                "title": "Section",
                "subtitle": "Bridge",
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.section_break.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.section_break.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.section_break.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.section_break.add_textbox") as add_textbox,
        ):
            render_section_break(self._ctx(), slide_data)
        self.assertEqual(add_textbox.call_count, 2)

    def test_render_title_only_renders_center_title(self):
        slide_data = TitleOnlySlide.model_validate(
            {
                "slide_id": "s6",
                "layout": "title_only",
                "title": "Executive Summary",
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.title_only.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.title_only.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.title_only.add_card"),
            patch("tools.sie_autoppt.v2.renderers.title_only.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.title_only.add_textbox") as add_textbox,
        ):
            render_title_only(self._ctx(), slide_data)
        add_textbox.assert_called_once()

    def test_render_timeline_calls_timeline_flow(self):
        slide_data = TimelineSlide.model_validate(
            {
                "slide_id": "s7",
                "layout": "timeline",
                "title": "Delivery Plan",
                "heading": "Phases",
                "stages": [{"title": "Q1", "detail": "Align"}, {"title": "Q2", "detail": "Pilot"}],
            }
        )
        with (
            patch("tools.sie_autoppt.v2.renderers.timeline.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.timeline.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.timeline.add_textbox"),
            patch("tools.sie_autoppt.v2.renderers.timeline.add_card"),
            patch("tools.sie_autoppt.v2.renderers.timeline.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.timeline.add_timeline_flow") as add_timeline_flow,
        ):
            render_timeline(self._ctx(), slide_data)
        add_timeline_flow.assert_called_once()

    def test_render_cards_grid_renders_card_body_text_for_non_empty_body(self):
        slide_data = CardsGridSlide.model_validate(
            {
                "slide_id": "s8",
                "layout": "cards_grid",
                "title": "Cards",
                "cards": [{"title": "A", "body": "B"}, {"title": "C", "body": ""}],
            }
        )
        fake_shape = Mock()
        fake_shape.fill.fore_color.rgb = None
        with (
            patch("tools.sie_autoppt.v2.renderers.cards_grid.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.cards_grid.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.cards_grid.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.cards_grid.cards_grid_positions", return_value=((1.0, 1.0, 2.0, 2.0), (3.5, 1.0, 2.0, 2.0))),
            patch("tools.sie_autoppt.v2.renderers.cards_grid.add_card", return_value=fake_shape),
            patch("tools.sie_autoppt.v2.renderers.cards_grid.add_textbox") as add_textbox,
        ):
            render_cards_grid(self._ctx(), slide_data)
        self.assertGreaterEqual(add_textbox.call_count, 3)

    def test_render_matrix_grid_renders_axes_and_cell_content(self):
        slide_data = MatrixGridSlide.model_validate(
            {
                "slide_id": "s9",
                "layout": "matrix_grid",
                "title": "Matrix",
                "heading": "Priorities",
                "x_axis": "Value",
                "y_axis": "Effort",
                "cells": [{"title": "A", "body": "B"}, {"title": "C", "body": "D"}],
            }
        )
        fake_shape = Mock()
        fake_shape.fill.fore_color.rgb = None
        with (
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.add_blank_slide", return_value=object()),
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.fill_background"),
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.add_page_number"),
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.resolve_matrix_grid_layout") as resolve_layout,
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.add_card", return_value=fake_shape),
            patch("tools.sie_autoppt.v2.renderers.matrix_grid.add_textbox") as add_textbox,
        ):
            resolve_layout.return_value = Mock(
                heading_top=1.2,
                x_axis_left=1.1,
                x_axis_top=6.1,
                x_axis_width=3.0,
                x_axis_height=0.3,
                y_axis_left=0.3,
                y_axis_top=2.0,
                y_axis_width=0.5,
                y_axis_height=2.5,
                outer_card=Mock(left=0.9, top=1.6, width=11.5, height=4.9),
                cell_positions=((1.1, 2.0), (4.0, 2.0), (6.9, 2.0), (9.8, 2.0)),
                cell_width=2.7,
                cell_height=2.1,
                palette_roles=("card_bg", "bg"),
                card_title_left_padding=0.2,
                card_title_top_padding=0.15,
                card_title_width=2.3,
                card_title_height=0.4,
                card_body_top_offset=0.6,
                card_body_width=2.3,
                card_body_height=1.3,
            )
            render_matrix_grid(self._ctx(), slide_data)
        self.assertGreaterEqual(add_textbox.call_count, 6)


if __name__ == "__main__":
    unittest.main()
