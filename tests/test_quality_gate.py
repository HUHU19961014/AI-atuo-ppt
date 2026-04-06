from __future__ import annotations

import pytest

from tools.sie_autoppt.v2.quality_checks import (
    WARNING_LEVEL_ERROR,
    WARNING_LEVEL_HIGH,
    WARNING_LEVEL_WARNING,
    check_deck_content,
    count_errors,
    count_by_level,
)
from tools.sie_autoppt.v2.schema import (
    DeckDocument,
    ThemeMeta,
    SectionBreakSlide,
    TitleContentSlide,
    TitleOnlySlide,
)


class TestQualityGate:
    def test_title_length_thresholds(self):
        """Test that title length triggers appropriate warning levels."""
        # 20 chars: no warning
        slide_20 = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="啊" * 20,  # 20 chars
            content=["test"],
        )
        warnings_20 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_20],
            )
        )
        assert len([w for w in warnings_20 if "title contains" in w.message]) == 0

        # 22 chars: warning
        slide_22 = TitleContentSlide(
            slide_id="s2",
            layout="title_content",
            title="啊" * 22,  # 22 chars
            content=["test"],
        )
        warnings_22 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_22],
            )
        )
        title_warnings_22 = [w for w in warnings_22 if "title contains" in w.message]
        assert len(title_warnings_22) == 1
        assert title_warnings_22[0].warning_level == WARNING_LEVEL_WARNING

        # 26 chars: high warning
        slide_26 = TitleContentSlide(
            slide_id="s3",
            layout="title_content",
            title="啊" * 26,  # 26 chars
            content=["test"],
        )
        warnings_26 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_26],
            )
        )
        title_warnings_26 = [w for w in warnings_26 if "title contains" in w.message]
        assert len(title_warnings_26) == 1
        assert title_warnings_26[0].warning_level == WARNING_LEVEL_HIGH

        # 30 chars: error
        slide_30 = TitleContentSlide(
            slide_id="s4",
            layout="title_content",
            title="啊" * 30,  # 30 chars
            content=["test"],
        )
        warnings_30 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_30],
            )
        )
        title_warnings_30 = [w for w in warnings_30 if "title contains" in w.message]
        assert len(title_warnings_30) == 1
        assert title_warnings_30[0].warning_level == WARNING_LEVEL_ERROR

    def test_directory_style_title_detection(self):
        """Test that directory-style titles are detected."""
        slide = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="建设背景",
            content=["test"],
        )
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide],
            )
        )
        directory_warnings = [w for w in warnings if "directory-style" in w.message]
        assert len(directory_warnings) == 1
        assert directory_warnings[0].warning_level == WARNING_LEVEL_WARNING

    def test_bullet_length_thresholds(self):
        """Test that bullet length triggers appropriate warning levels."""
        # 35 chars: no warning
        slide_35 = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="Test",
            content=["啊" * 35],  # 35 chars
        )
        warnings_35 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_35],
            )
        )
        bullet_warnings_35 = [w for w in warnings_35 if "bullet" in w.message and "length" in w.message]
        assert len(bullet_warnings_35) == 0

        # 40 chars: warning
        slide_40 = TitleContentSlide(
            slide_id="s2",
            layout="title_content",
            title="Test",
            content=["啊" * 40],  # 40 chars
        )
        warnings_40 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_40],
            )
        )
        bullet_warnings_40 = [w for w in warnings_40 if "bullet" in w.message and "length" in w.message]
        assert len(bullet_warnings_40) == 1
        assert bullet_warnings_40[0].warning_level == WARNING_LEVEL_WARNING

        # 55 chars: error
        slide_55 = TitleContentSlide(
            slide_id="s3",
            layout="title_content",
            title="Test",
            content=["啊" * 55],  # 55 chars
        )
        warnings_55 = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide_55],
            )
        )
        bullet_warnings_55 = [w for w in warnings_55 if "bullet" in w.message and "length" in w.message]
        assert len(bullet_warnings_55) == 1
        assert bullet_warnings_55[0].warning_level == WARNING_LEVEL_ERROR

    def test_structure_checks(self):
        """Test that deck structure is validated."""
        # Good structure: section_break first, title_only last
        good_deck = DeckDocument(
            meta=ThemeMeta(title="Test", theme="business_red"),
            slides=[
                SectionBreakSlide(slide_id="s1", layout="section_break", title="Start", subtitle="Begin"),
                TitleContentSlide(slide_id="s2", layout="title_content", title="Middle", content=["test"]),
                TitleOnlySlide(slide_id="s3", layout="title_only", title="End"),
            ],
        )
        warnings_good = check_deck_content(good_deck)
        structure_warnings_good = [w for w in warnings_good if "first slide" in w.message or "last slide" in w.message]
        assert len(structure_warnings_good) == 0

        # Bad structure: title_content first and last
        bad_deck = DeckDocument(
            meta=ThemeMeta(title="Test", theme="business_red"),
            slides=[
                TitleContentSlide(slide_id="s1", layout="title_content", title="Start", content=["test"]),
                TitleContentSlide(slide_id="s2", layout="title_content", title="End", content=["test"]),
            ],
        )
        warnings_bad = check_deck_content(bad_deck)
        structure_warnings_bad = [w for w in warnings_bad if "first slide" in w.message or "last slide" in w.message]
        assert len(structure_warnings_bad) == 2

    def test_count_errors(self):
        """Test error counting utility."""
        slide = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="啊" * 30,  # 30 chars - error
            content=["啊" * 55],  # 55 chars - error
        )
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide],
            )
        )
        assert count_errors(warnings) == 2

    def test_count_by_level(self):
        """Test warning level counting utility."""
        slide = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="啊" * 26,  # 26 chars - high
            content=[
                "啊" * 40,  # 40 chars - warning
                "test",
            ],
        )
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide],
            )
        )
        counts = count_by_level(warnings)
        assert counts[WARNING_LEVEL_ERROR] == 0
        assert counts[WARNING_LEVEL_HIGH] == 1
        assert counts[WARNING_LEVEL_WARNING] >= 1  # At least the bullet warning
