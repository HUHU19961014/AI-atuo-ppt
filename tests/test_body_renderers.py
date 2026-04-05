import copy
import unittest
from dataclasses import replace

from pptx import Presentation

from tools.sie_autoppt.body_renderers import fill_body_slide
from tools.sie_autoppt.config import DEFAULT_TEMPLATE
from tools.sie_autoppt.models import BodyPageSpec
from tools.sie_autoppt.template_manifest import load_template_manifest


class BodyRendererTests(unittest.TestCase):
    def test_fill_body_slide_reports_context_when_manifest_field_is_missing(self):
        manifest = load_template_manifest()
        broken_layouts = copy.deepcopy(manifest.render_layouts)
        del broken_layouts["general_business"]["origin_left"]
        broken_manifest = replace(manifest, render_layouts=broken_layouts)

        presentation = Presentation(str(DEFAULT_TEMPLATE))
        slide = presentation.slides[manifest.slide_roles.body_template]
        page = BodyPageSpec(
            page_key="p1",
            title="测试页",
            subtitle="副标题",
            bullets=["要点一", "要点二"],
            pattern_id="general_business",
        )

        with self.assertRaises(KeyError) as ctx:
            fill_body_slide(slide, page, broken_manifest)

        message = str(ctx.exception)
        self.assertIn("origin_left", message)
        self.assertIn("render_layouts.general_business", message)
