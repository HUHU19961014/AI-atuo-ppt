import unittest
import shutil
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from tools.sie_autoppt.v2 import theme_loader
from tools.sie_autoppt.v2.layout_ids import SUPPORTED_LAYOUTS as LAYOUT_ID_SOURCE
from tools.sie_autoppt.v2.layout_router import LAYOUT_RENDERERS
from tools.sie_autoppt.v2.schema import (
    OutlineDocument,
    SUPPORTED_LAYOUTS,
    SUPPORTED_THEMES,
    ThemeMeta,
    collect_deck_warnings,
    validate_deck_payload,
)
from tools.sie_autoppt.v2.io import (
    is_semantic_deck_document,
    load_deck_document,
    load_outline_document,
    write_outline_document,
)

try:
    from hypothesis import given, strategies as st
except ImportError:  # pragma: no cover
    given = None
    st = None


@contextmanager
def _workspace_tmpdir():
    root = Path(__file__).resolve().parents[1] / ".tmp_test_workspace"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tmp_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class V2SchemaTests(unittest.TestCase):
    def test_supported_themes_are_discovered_from_theme_directory(self):
        for theme_name in (
            "business_red",
            "tech_blue",
            "fresh_green",
            "google_brand_light",
            "anthropic_orange",
            "mckinsey_blue",
            "consulting_navy",
            "sie_consulting_fixed",
        ):
            self.assertIn(theme_name, SUPPORTED_THEMES)

    def test_available_theme_names_raises_for_missing_theme_directory(self):
        with _workspace_tmpdir() as temp_dir:
            missing_dir = Path(temp_dir) / "missing-themes"
            with patch.object(theme_loader, "THEMES_DIR", missing_dir):
                with self.assertRaises(FileNotFoundError):
                    theme_loader.available_theme_names()

    def test_supported_layouts_are_renderable(self):
        self.assertIs(SUPPORTED_LAYOUTS, LAYOUT_ID_SOURCE)
        self.assertEqual(set(SUPPORTED_LAYOUTS), set(LAYOUT_RENDERERS))

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

    def test_write_outline_document_preserves_strategy_metadata(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Decision Context", "goal": "Define the decision context and constraint."},
                    {"page_no": 2, "title": "Execution Path", "goal": "Describe the execution route and ownership."},
                    {"page_no": 3, "title": "Recommended Path", "goal": "Close with recommendation and milestone."},
                ],
                "story_rationale": "Lead with decision context, then execution tradeoffs, then owner-backed close.",
                "outline_strategy": {
                    "chapter_count": 3,
                    "audience_tier": "executive",
                    "narrative_pacing": "balanced",
                },
            }
        )

        with _workspace_tmpdir() as temp_dir:
            output_path = Path(temp_dir) / "outline.json"
            write_outline_document(outline, output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            loaded = load_outline_document(output_path)

        self.assertIn("story_rationale", payload)
        self.assertIn("outline_strategy", payload)
        self.assertEqual(payload["outline_strategy"]["narrative_pacing"], "balanced")
        self.assertEqual(loaded.story_rationale, outline.story_rationale)
        self.assertEqual(loaded.outline_strategy.narrative_pacing, "balanced")

    def test_validate_deck_payload_normalizes_defaults_and_collects_warnings(self):
        validated = validate_deck_payload(
            {
                "meta": {"theme": "google_brand_light"},
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

    def test_validate_deck_payload_accepts_specialized_layouts(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Sample Deck", "theme": "google_brand_light", "language": "en", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "layout": "timeline",
                        "title": "Roadmap",
                        "stages": [
                            {"title": "Q1", "detail": "Align scope"},
                            {"title": "Q2", "detail": "Build workflows"},
                        ],
                    },
                    {
                        "layout": "stats_dashboard",
                        "title": "KPI Dashboard",
                        "metrics": [
                            {"label": "OTD", "value": "95%"},
                            {"label": "Yield", "value": "98%"},
                        ],
                    },
                    {
                        "layout": "matrix_grid",
                        "title": "Risk Matrix",
                        "cells": [
                            {"title": "Low-Low", "body": "Monitor"},
                            {"title": "High-High", "body": "Escalate"},
                        ],
                    },
                    {
                        "layout": "cards_grid",
                        "title": "Capabilities",
                        "cards": [
                            {"title": "Plan", "body": "Align work"},
                            {"title": "Operate", "body": "Close loop"},
                        ],
                    },
                ],
            }
        )

        self.assertEqual(validated.deck.slides[0].layout, "timeline")
        self.assertEqual(validated.deck.slides[1].layout, "stats_dashboard")
        self.assertEqual(validated.deck.slides[2].layout, "matrix_grid")
        self.assertEqual(validated.deck.slides[3].layout, "cards_grid")

    def test_validate_deck_payload_strips_nested_optional_fields(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_image",
                        "title": "Architecture",
                        "anti_argument": "   ",
                        "content": ["  Point A  ", " Point B "],
                        "image": {"mode": "placeholder", "caption": "  Diagram  ", "path": "   "},
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertIsNone(slide.anti_argument)
        self.assertEqual(slide.content, ["Point A", "Point B"])
        self.assertEqual(slide.image.caption, "Diagram")
        self.assertIsNone(slide.image.path)

    def test_validate_deck_payload_strips_stats_dashboard_heading_and_note(self):
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "stats_dashboard",
                        "title": "Metrics",
                        "heading": "  Weekly KPI  ",
                        "metrics": [
                            {"label": " OTD ", "value": " 95% ", "note": "  Stable  "},
                            {"label": " Yield ", "value": " 98% ", "note": "   "},
                        ],
                    }
                ],
            }
        )

        slide = validated.deck.slides[0]
        self.assertEqual(slide.heading, "Weekly KPI")
        self.assertEqual(slide.metrics[0].label, "OTD")
        self.assertEqual(slide.metrics[0].value, "95%")
        self.assertEqual(slide.metrics[0].note, "Stable")
        self.assertIsNone(slide.metrics[1].note)

    def test_load_deck_document_accepts_semantic_deck_json(self):
        semantic_payload = {
            "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "结论",
                    "intent": "conclusion",
                    "blocks": [{"kind": "statement", "text": "先打通主链，再扩展到运营闭环。"}],
                }
            ],
        }
        with _workspace_tmpdir() as temp_dir:
            deck_path = Path(temp_dir) / "semantic.json"
            deck_path.write_text(__import__("json").dumps(semantic_payload, ensure_ascii=False), encoding="utf-8")
            deck = load_deck_document(deck_path)

        self.assertEqual(deck.slides[0].layout, "title_only")

    def test_is_semantic_deck_document_detects_semantic_json(self):
        semantic_payload = {
            "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "Lead with the decision."}]}],
        }
        with _workspace_tmpdir() as temp_dir:
            deck_path = Path(temp_dir) / "semantic.json"
            deck_path.write_text(__import__("json").dumps(semantic_payload, ensure_ascii=False), encoding="utf-8")

            self.assertTrue(is_semantic_deck_document(deck_path))

    def test_v2_json_loaders_accept_utf8_bom_files(self):
        with _workspace_tmpdir() as temp_dir:
            outline_path = Path(temp_dir) / "outline.json"
            outline_path.write_bytes(
                b"\xef\xbb\xbf"
                + __import__("json").dumps(
                    {"pages": [{"page_no": 1, "title": "Context", "goal": "Set context."}]},
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            deck_path = Path(temp_dir) / "semantic.json"
            deck_path.write_bytes(
                b"\xef\xbb\xbf"
                + __import__("json").dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [
                            {
                                "slide_id": "s1",
                                "title": "Conclusion",
                                "intent": "conclusion",
                                "blocks": [{"kind": "statement", "text": "Lead with the core decision."}],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
            )

            outline = load_outline_document(outline_path)
            deck = load_deck_document(deck_path)

        self.assertEqual(outline.pages[0].title, "Context")
        self.assertEqual(deck.slides[0].layout, "title_only")

    @unittest.skipIf(given is None or st is None, "hypothesis is not installed")
    def test_theme_meta_title_property(self):
        @given(st.text(min_size=1, max_size=80))
        def _property(title: str):
            meta = ThemeMeta.model_validate(
                {
                    "title": title,
                    "theme": "business_red",
                    "language": "zh-CN",
                    "author": "AI",
                    "version": "2.0",
                }
            )
            self.assertGreaterEqual(len(meta.title), 1)
            self.assertLessEqual(len(meta.title), 80)

        _property()
