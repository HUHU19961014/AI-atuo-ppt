import unittest

from tools.sie_autoppt.v2.quality_checks import check_deck_content
from tools.sie_autoppt.v2.schema import validate_deck_payload


class V2QualityChecksTests(unittest.TestCase):
    def test_content_checks_emit_structured_warnings(self):
        validated = validate_deck_payload(
            {
                "meta": {
                    "title": "测试告警",
                    "theme": "business_red",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "这是一个明显过长而且超过二十四个汉字的标题用于测试",
                        "content": [
                            "第一条内容明显过长，用于验证单条 bullet 超过四十字符后的告警提示。",
                        ],
                    },
                    {
                        "slide_id": "s2",
                        "layout": "two_columns",
                        "title": "双栏页",
                        "left": {
                            "heading": "左栏",
                            "items": ["1", "2", "3", "4", "5", "6"],
                        },
                        "right": {
                            "heading": "右栏",
                            "items": ["1"],
                        },
                    },
                    {
                        "slide_id": "s3",
                        "layout": "title_image",
                        "title": "图片页",
                        "content": [
                            "第一条内容较长，用于校验 title_image 的长度告警机制是否生效。",
                            "第二条",
                            "第三条",
                            "第四条",
                            "第五条",
                        ],
                        "image": {"mode": "placeholder", "caption": "test"},
                    },
                ],
            }
        )

        warnings = check_deck_content(validated.deck)

        self.assertTrue(any(item.slide_id == "s1" and item.warning_level == "warning" for item in warnings))
        self.assertTrue(any("bullet items" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s2" and "left column" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s2" and "count gap" in item.message for item in warnings))
        self.assertTrue(any(item.slide_id == "s3" and "exceeds 4" in item.message for item in warnings))
