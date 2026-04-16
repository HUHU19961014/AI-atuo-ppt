import unittest
from unittest.mock import patch

from tools.sie_autoppt.reference_styles import fill_reference_style_slide
from tools.sie_autoppt.models import BodyPageSpec


class ReferenceStylesPayloadValidationTests(unittest.TestCase):
    def test_fill_reference_style_slide_validates_payload_before_branching(self):
        page = BodyPageSpec(
            page_key="p1",
            title="Title",
            subtitle="Sub",
            bullets=["a"],
            pattern_id="kpi_dashboard",
            reference_style_id=None,
            payload={"metrics": [{"label": "OTD", "value": "95%"}]},
        )
        with patch("tools.sie_autoppt.reference_styles.validate_body_page_payload") as validate_payload:
            result = fill_reference_style_slide(slide=None, page=page)
        self.assertFalse(result)
        validate_payload.assert_called_once()

