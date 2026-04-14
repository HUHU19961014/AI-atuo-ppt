import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt.v2.io import write_deck_document
from tools.sie_autoppt.v2.schema import validate_deck_payload
from tools.sie_autoppt.v2.visual_review import (
    EXTENDED_REVIEW_DIMENSIONS,
    VISUAL_REVIEW_DIMENSIONS,
    _build_quality_gate_note,
    _patch_developer_prompt,
    _review_developer_prompt,
    _score_rating,
    apply_patch_set,
    export_slide_previews,
    iterate_visual_review,
    review_rendered_deck,
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
        self.assertIn("structure", prompt)
        self.assertIn("brand_consistency", prompt)
        self.assertIn("audience_fit", prompt)
        self.assertIn("正文建议 >= 16pt", prompt)
        self.assertIn("summary", prompt)
        self.assertIn("narrative closure", prompt)
        self.assertIn("rule-based quality-gate findings", prompt)

    def test_visual_review_schema_uses_dimension_registry(self):
        schema = __import__("tools.sie_autoppt.v2.visual_review", fromlist=["build_visual_review_schema"]).build_visual_review_schema()
        score_properties = schema["properties"]["scores"]["properties"]
        issue_dimension_enum = schema["properties"]["page_issues"]["items"]["properties"]["dimension"]["enum"]

        self.assertEqual(tuple(score_properties), tuple(dimension.key for dimension in VISUAL_REVIEW_DIMENSIONS))
        self.assertEqual(tuple(issue_dimension_enum), tuple(dimension.key for dimension in VISUAL_REVIEW_DIMENSIONS))
        self.assertEqual(VISUAL_REVIEW_DIMENSIONS, EXTENDED_REVIEW_DIMENSIONS)

    def test_patch_prompt_requires_blocker_only_fixes(self):
        prompt = _patch_developer_prompt()
        self.assertIn("仅针对 blocker 级别的问题生成", prompt)
        self.assertIn("每个 blocker 至少对应一个 patch 对象", prompt)
        self.assertIn("不要为 warning 生成 patch", prompt)

    def test_quality_gate_note_summarizes_issues(self):
        deck = validate_deck_payload(
            {
                "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {"slide_id": "s1", "layout": "title_only", "title": "项目背景"},
                    {"slide_id": "s2", "layout": "title_only", "title": "谢谢"},
                ],
            }
        ).deck
        note = _build_quality_gate_note(
            __import__("tools.sie_autoppt.v2.quality_checks", fromlist=["quality_gate"]).quality_gate(deck)
        )

        self.assertIn("Rule-based quality gate findings", note)
        self.assertIn("[s1]", note)
        self.assertIn("[s2]", note)

    def test_review_rendered_deck_includes_quality_gate_findings_in_user_items(self):
        deck = validate_deck_payload(
            {
                "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {"slide_id": "s1", "layout": "title_only", "title": "项目背景"},
                    {"slide_id": "s2", "layout": "title_only", "title": "谢谢"},
                ],
            }
        ).deck
        captured: dict[str, object] = {}

        class FakeClient:
            def create_structured_json_with_user_items(self, **kwargs):
                captured.update(kwargs)
                return {
                    "scores": {
                        "structure": 3,
                        "title_quality": 3,
                        "content_density": 3,
                        "layout_stability": 3,
                        "deliverability": 3,
                    },
                    "total": 15,
                    "rating": "可用初稿",
                    "page_issues": [],
                    "summary": "Needs refinement.",
                }

        with (
            patch("tools.sie_autoppt.v2.visual_review.load_openai_responses_config"),
            patch("tools.sie_autoppt.v2.visual_review.OpenAIResponsesClient", return_value=FakeClient()),
        ):
            review_rendered_deck(deck, previews=[], model="test-model")

        user_items = captured["user_items"]
        self.assertIn("Rule-based quality gate findings", user_items[0]["text"])
        self.assertIn("generic-background", user_items[0]["text"])
        self.assertIn("generic closing or thanks", user_items[0]["text"])

    def test_review_rendered_deck_marks_preview_mode(self):
        deck = _sample_deck()

        class FakeClient:
            def create_structured_json_with_user_items(self, **kwargs):
                return {
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
                    "summary": "Looks stable.",
                }

        with (
            patch("tools.sie_autoppt.v2.visual_review.load_openai_responses_config"),
            patch("tools.sie_autoppt.v2.visual_review.OpenAIResponsesClient", return_value=FakeClient()),
            patch("tools.sie_autoppt.v2.visual_review.platform.system", return_value="Windows"),
        ):
            review = review_rendered_deck(deck, previews=[Path("slide1.png")], model="test-model")

        self.assertEqual(review["preview_mode"], "powerpoint")

    def test_score_rating_mapping(self):
        self.assertEqual(_score_rating(22), "优秀")
        self.assertEqual(_score_rating(18), "合格")
        self.assertEqual(_score_rating(12), "可用初稿")
        self.assertEqual(_score_rating(8), "质量偏弱")
        self.assertEqual(_score_rating(5), "不合格")
        self.assertEqual(_score_rating(38, max_score=45), "优秀")
        self.assertEqual(_score_rating(29, max_score=45), "合格")

    def test_review_rendered_deck_accepts_provider_injection(self):
        deck = _sample_deck()

        class FakeProvider:
            def __init__(self):
                self.calls = []

            def create_structured_json_with_user_items(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "scores": {dimension.key: 4 for dimension in VISUAL_REVIEW_DIMENSIONS},
                    "total": 1,
                    "rating": "不合格",
                    "page_issues": [],
                    "summary": "Provider injected.",
                }

        provider = FakeProvider()
        with patch("tools.sie_autoppt.v2.visual_review.OpenAIResponsesClient") as client_mock:
            review = review_rendered_deck(deck, previews=[], provider=provider)

        client_mock.assert_not_called()
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(review["total"], len(VISUAL_REVIEW_DIMENSIONS) * 4)

    def test_generate_blocker_patches_accepts_provider_injection(self):
        from tools.sie_autoppt.v2.visual_review import generate_blocker_patches

        deck = _sample_deck()

        class FakeProvider:
            def __init__(self):
                self.calls = []

            def create_structured_json_with_user_items(self, **kwargs):
                self.calls.append(kwargs)
                return {"patches": []}

        provider = FakeProvider()
        with patch("tools.sie_autoppt.v2.visual_review.OpenAIResponsesClient") as client_mock:
            patches = generate_blocker_patches(
                deck,
                {
                    "page_issues": [
                        {"page": 1, "level": "blocker", "dimension": "layout_stability", "issue": "Overflow", "suggestion": "Compress"}
                    ]
                },
                provider=provider,
            )

        client_mock.assert_not_called()
        self.assertEqual(patches, {"patches": []})
        self.assertEqual(len(provider.calls), 1)

    def test_export_slide_previews_skips_when_soffice_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pptx_path = Path(temp_dir) / "deck.pptx"
            pptx_path.write_bytes(b"fake-pptx")
            with (
                patch("tools.sie_autoppt.v2.visual_review.platform.system", return_value="Linux"),
                patch("tools.sie_autoppt.v2.visual_review.shutil.which", return_value=None),
            ):
                previews = export_slide_previews(pptx_path, Path(temp_dir) / "previews")

        self.assertEqual(previews, [])

    def test_export_slide_previews_passes_timeout_to_subprocess(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pptx_path = Path(temp_dir) / "deck.pptx"
            pptx_path.write_bytes(b"fake-pptx")
            output_dir = Path(temp_dir) / "previews"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "slide1.png").write_bytes(b"png")
            completed = type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with (
                patch("tools.sie_autoppt.v2.visual_review.platform.system", return_value="Linux"),
                patch("tools.sie_autoppt.v2.visual_review.shutil.which", return_value="soffice"),
                patch("tools.sie_autoppt.v2.visual_review.subprocess.run", return_value=completed) as run_mock,
            ):
                export_slide_previews(pptx_path, output_dir)

        self.assertIn("timeout", run_mock.call_args.kwargs)

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

    def test_apply_patch_set_accepts_jsonpath_style_fields(self):
        deck = _sample_deck()
        patched = apply_patch_set(
            deck,
            {
                "patches": [
                    {"page": 1, "field": "$.slides[0].title", "old_value": "第一页", "new_value": "结论页", "reason": "更结论导向"},
                    {"page": 2, "field": "$.slides[1].right.items[0]", "old_value": "右一", "new_value": "右一精简", "reason": "压缩文案"},
                ]
            },
        )

        self.assertEqual(patched.slides[0].title, "结论页")
        self.assertEqual(patched.slides[1].right.items[0], "右一精简")

    def test_apply_patch_set_rejects_page_mismatch(self):
        deck = _sample_deck()
        with self.assertRaisesRegex(ValueError, "does not match field path"):
            apply_patch_set(
                deck,
                {
                    "patches": [
                        {"page": 2, "field": "slides[0].title", "old_value": "第一页", "new_value": "结论页", "reason": "页码错误"}
                    ]
                },
            )

    def test_apply_patch_set_rejects_old_value_mismatch(self):
        deck = _sample_deck()
        with self.assertRaisesRegex(ValueError, "old_value mismatch"):
            apply_patch_set(
                deck,
                {
                    "patches": [
                        {"page": 1, "field": "slides[0].title", "old_value": "错误旧值", "new_value": "结论页", "reason": "旧值不匹配"}
                    ]
                },
            )

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
            self.assertEqual(result.preview_mode, "powerpoint")

        self.assertTrue(result.review_path.name.endswith(".json"))
        self.assertTrue(result.patch_path.name.endswith(".json"))

    def test_review_once_passes_preview_fallback_note_when_previews_are_missing(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)
            fake_render = type(
                "FakeRender",
                (),
                {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck},
            )()
            captured: dict[str, object] = {}

            def fake_review(deck_data, previews, *, model=None, preview_note=None):
                captured["deck"] = deck_data
                captured["previews"] = previews
                captured["preview_note"] = preview_note
                return {
                    "scores": {
                        "structure": 4,
                        "title_quality": 4,
                        "content_density": 4,
                        "layout_stability": 3,
                        "deliverability": 3,
                    },
                    "total": 18,
                    "rating": "合格",
                    "page_issues": [],
                    "summary": "Fallback review path.",
                }

            with (
                patch("tools.sie_autoppt.v2.visual_review.generate_ppt", return_value=fake_render),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", return_value=[]),
                patch("tools.sie_autoppt.v2.visual_review.review_rendered_deck", side_effect=fake_review),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                review_deck_once(deck_path=deck_path, output_dir=Path(temp_dir) / "review")

        self.assertEqual(captured["previews"], [])
        self.assertIn("LibreOffice", str(captured["preview_note"]))

    def test_review_once_falls_back_when_preview_export_raises(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)
            fake_render = type(
                "FakeRender",
                (),
                {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck},
            )()
            captured: dict[str, object] = {}

            def fake_review(deck_data, previews, *, model=None, preview_note=None):
                captured["previews"] = previews
                captured["preview_note"] = preview_note
                return {
                    "scores": {
                        "structure": 4,
                        "title_quality": 4,
                        "content_density": 4,
                        "layout_stability": 2,
                        "deliverability": 2,
                    },
                    "total": 16,
                    "rating": "合格",
                    "page_issues": [],
                    "summary": "Fallback review path.",
                }

            with (
                patch("tools.sie_autoppt.v2.visual_review.generate_ppt", return_value=fake_render),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", side_effect=RuntimeError("PowerPoint COM unavailable")),
                patch("tools.sie_autoppt.v2.visual_review.review_rendered_deck", side_effect=fake_review),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                result = review_deck_once(deck_path=deck_path, output_dir=Path(temp_dir) / "review")

        self.assertEqual(captured["previews"], [])
        self.assertIn("PowerPoint COM unavailable", str(captured["preview_note"]))
        self.assertEqual(result.preview_mode, "content_only")

    def test_review_once_falls_back_when_preview_export_times_out(self):
        deck = _sample_deck()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_document(deck, deck_path)
            fake_render = type(
                "FakeRender",
                (),
                {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": deck},
            )()
            captured: dict[str, object] = {}

            def fake_review(deck_data, previews, *, model=None, preview_note=None):
                captured["previews"] = previews
                captured["preview_note"] = preview_note
                return {
                    "scores": {
                        "structure": 3,
                        "title_quality": 3,
                        "content_density": 3,
                        "layout_stability": 2,
                        "deliverability": 2,
                    },
                    "total": 13,
                    "rating": "可用初稿",
                    "page_issues": [],
                    "summary": "Fallback after timeout.",
                }

            with (
                patch("tools.sie_autoppt.v2.visual_review.generate_ppt", return_value=fake_render),
                patch(
                    "tools.sie_autoppt.v2.visual_review.export_slide_previews",
                    side_effect=subprocess.TimeoutExpired(cmd="soffice", timeout=10),
                ),
                patch("tools.sie_autoppt.v2.visual_review.review_rendered_deck", side_effect=fake_review),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                review_deck_once(deck_path=deck_path, output_dir=Path(temp_dir) / "review")

        self.assertEqual(captured["previews"], [])
        self.assertIn("timed out", str(captured["preview_note"]).lower())
    def test_review_once_preserves_semantic_input_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_path = Path(temp_dir) / "semantic.json"
            semantic_path.write_text(
                __import__("json").dumps(
                    {
                        "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [
                            {
                                "slide_id": "s1",
                                "title": "Conclusion",
                                "intent": "conclusion",
                                "blocks": [{"kind": "statement", "text": "Lead with the decision."}],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_render = type(
                "FakeRender",
                (),
                {"output_path": Path(temp_dir) / "deck.pptx", "final_deck": validate_deck_payload({"meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"}, "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Conclusion"}]}).deck},
            )()

            with (
                patch("tools.sie_autoppt.v2.visual_review.generate_ppt", return_value=fake_render),
                patch("tools.sie_autoppt.v2.visual_review.export_slide_previews", return_value=[Path(temp_dir) / "slide1.png"]),
                patch(
                    "tools.sie_autoppt.v2.visual_review.review_rendered_deck",
                    return_value={
                        "scores": {"structure": 4, "title_quality": 4, "content_density": 4, "layout_stability": 4, "deliverability": 4},
                        "total": 20,
                        "rating": "鍚堟牸",
                        "page_issues": [],
                        "summary": "鏁翠綋绋冲畾锛屽彲缁х画浣滀负娴嬭瘯鏍蜂緥銆?",
                    },
                ),
                patch("tools.sie_autoppt.v2.visual_review.generate_blocker_patches", return_value={"patches": []}),
            ):
                result = review_deck_once(deck_path=semantic_path, output_dir=Path(temp_dir) / "review")

            self.assertIsNotNone(result.semantic_source_path)
            self.assertTrue(result.semantic_source_path.exists())

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
                    "page_issues": [{"page": 1, "level": "blocker", "dimension": "title_quality", "issue": "标题偏目录化", "suggestion": "改成结论式标题"}],
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
                        "page_issues": [{"page": 1, "level": "blocker", "dimension": "layout_stability", "issue": "正文溢出边界", "suggestion": "压缩文案并调整布局"}],
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


