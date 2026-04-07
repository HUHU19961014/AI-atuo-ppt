import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt.v2.io import write_deck_document
from tools.sie_autoppt.v2.schema import validate_deck_payload
from tools.sie_autoppt.v2.visual_review import (
    _patch_developer_prompt,
    _review_developer_prompt,
    _score_rating,
    apply_patch_set,
    iterate_visual_review,
    review_deck_once,
)


def _sample_deck():
    return validate_deck_payload(
        {
            "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {"slide_id": "s1", "layout": "title_content", "title": "第一页", "content": ["要点一", "要点二"]},
                {
                    "slide_id": "s2",
                    "layout": "two_columns",
                    "title": "第二页",
                    "left": {"heading": "左侧", "items": ["左一", "左二"]},
                    "right": {"heading": "右侧", "items": ["右一", "右二"]},
                },
            ],
        }
    ).deck


class V2VisualReviewTests(unittest.TestCase):
    def test_review_prompt_includes_explicit_scorecard(self):
        prompt = _review_developer_prompt()
        self.assertIn("结构与页数合理性", prompt)
        self.assertIn("标题自然度", prompt)
        self.assertIn("正文建议 >= 16pt", prompt)
        self.assertIn("summary 用 2-3 句中文概括整体判断", prompt)

    def test_patch_prompt_requires_blocker_only_fixes(self):
        prompt = _patch_developer_prompt()
        self.assertIn("仅针对 blocker 级别的问题生成", prompt)
        self.assertIn("每个 blocker 至少对应一个 patch 对象", prompt)
        self.assertIn("不要为 warning 生成 patch", prompt)

    def test_score_rating_mapping(self):
        self.assertEqual(_score_rating(22), "优秀")
        self.assertEqual(_score_rating(18), "合格")
        self.assertEqual(_score_rating(12), "可用初稿")
        self.assertEqual(_score_rating(8), "质量偏弱")
        self.assertEqual(_score_rating(5), "不合格")

    def test_apply_patch_set_updates_nested_fields(self):
        deck = _sample_deck()
        patched = apply_patch_set(
            deck,
            {
                "patches": [
                    {"page": 1, "field": "slides[0].title", "old_value": "第一页", "new_value": "结论页", "reason": "更结论导向"},
                    {"page": 2, "field": "slides[1].left.items[1]", "old_value": "左二", "new_value": "左二精简", "reason": "压缩文案"},
                ]
            },
        )

        self.assertEqual(patched.slides[0].title, "结论页")
        self.assertEqual(patched.slides[1].left.items[1], "左二精简")

    def test_review_once_writes_review_and_patch_outputs(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)
            fake_render = type(
                "FakeRender",
                (),
                {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck},
            )()

            with (
                patch("tools.sie_autoppt.v2.visual_review.generate_ppt", return_value=fake_render),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", return_value=[Path(temp_dir) / "slide1.png"]),
                patch(
                    "tools.sie_autoppt.v2.visual_review.review_rendered_deck",
                    return_value={
                        "scores": {
                            "structure": 4,
                            "title_quality": 4,
                            "content_density": 4,
                            "layout_stability": 4,
                            "deliverability": 4,
                        },
                        "total": 20,
                        "rating": "合格",
                        "page_issues": [],
                        "summary": "整体稳定，可继续作为测试样例。",
                    },
                ),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                result = review_deck_once(deck_path=deck_path, output_dir=Path(temp_dir) / "review")

            self.assertTrue(result.review_path.exists())
            self.assertTrue(result.patch_path.exists())

        self.assertTrue(result.review_path.name.endswith(".json"))
        self.assertTrue(result.patch_path.name.endswith(".json"))

    def test_iterate_visual_review_applies_blocker_patches(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)

            review_results = [
                {
                    "scores": {"structure": 3, "title_quality": 3, "content_density": 3, "layout_stability": 2, "deliverability": 2},
                    "total": 13,
                    "rating": "可用初稿",
                    "page_issues": [{"page": 1, "level": "blocker", "dimension": "title", "issue": "标题偏目录化", "suggestion": "改成结论式标题"}],
                    "summary": "第一页标题需要更结论化，才能支撑正式汇报语气。",
                },
                {
                    "scores": {"structure": 4, "title_quality": 4, "content_density": 4, "layout_stability": 4, "deliverability": 4},
                    "total": 20,
                    "rating": "合格",
                    "page_issues": [],
                    "summary": "主要 blocker 已消除，整体质量明显改善。",
                },
            ]
            patch_results = [
                {"patches": [{"page": 1, "field": "slides[0].title", "old_value": "第一页", "new_value": "第一页结论", "reason": "让标题更结论化"}]},
                {"patches": []},
            ]

            with (
                patch(
                    "tools.sie_autoppt.v2.visual_review.generate_ppt",
                    side_effect=lambda deck_data, **_: type(
                        "FakeRender",
                        (),
                        {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck_data},
                    )(),
                ),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", return_value=[Path(temp_dir) / "slide1.png"]),
                patch("tools.sie_autoppt.v2.visual_review.review_rendered_deck", side_effect=review_results),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", side_effect=patch_results),
            ):
                result = iterate_visual_review(deck_path=deck_path, output_dir=Path(temp_dir) / "loop", max_rounds=2)

            final_deck = validate_deck_payload(json_load(result.deck_path)).deck
            self.assertTrue(result.final_review_path.exists())
            self.assertTrue(result.final_patch_path.exists())

        self.assertEqual(final_deck.slides[0].title, "第一页结论")

    def test_iterate_visual_review_raises_when_blockers_have_no_patches(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)

            with (
                patch(
                    "tools.sie_autoppt.v2.visual_review.generate_ppt",
                    side_effect=lambda deck_data, **_: type(
                        "FakeRender",
                        (),
                        {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck_data},
                    )(),
                ),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", return_value=[Path(temp_dir) / "slide1.png"]),
                patch(
                    "tools.sie_autoppt.v2.visual_review.review_rendered_deck",
                    return_value={
                        "scores": {"structure": 3, "title_quality": 2, "content_density": 3, "layout_stability": 2, "deliverability": 2},
                        "total": 12,
                        "rating": "可用初稿",
                        "page_issues": [{"page": 1, "level": "blocker", "dimension": "layout", "issue": "正文溢出边界", "suggestion": "压缩文案并调整布局"}],
                        "summary": "当前仍有 blocker，不能视为可交付。",
                    },
                ),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                with self.assertRaises(RuntimeError):
                    iterate_visual_review(deck_path=deck_path, output_dir=Path(temp_dir) / "loop", max_rounds=1)


def json_load(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
