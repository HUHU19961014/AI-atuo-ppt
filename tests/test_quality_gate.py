from __future__ import annotations

import pytest

from tools.sie_autoppt.v2.quality_checks import (
    WARNING_LEVEL_ERROR,
    WARNING_LEVEL_HIGH,
    WARNING_LEVEL_WARNING,
    check_deck_content,
    count_errors,
    count_by_level,
    quality_gate,
)
from tools.sie_autoppt.v2.schema import (
    ColumnBlock,
    DeckDocument,
    MetricEntry,
    StatsDashboardSlide,
    ThemeMeta,
    SectionBreakSlide,
    TimelineSlide,
    TitleContentSlide,
    TitleOnlySlide,
    TwoColumnsSlide,
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
                TitleOnlySlide(slide_id="s3", layout="title_only", title="Next Step"),
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
        assert len(structure_warnings_bad) == 3

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

    def test_quality_gate_requires_review_for_high_only(self):
        gate_result = quality_gate(
            {
                "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "测" * 26,
                        "content": ["test"],
                    }
                ],
            }
        )
        assert gate_result.passed is True
        assert gate_result.review_required is True
        assert gate_result.summary["high_count"] == 1
        assert gate_result.summary["error_count"] == 0

    def test_quality_gate_blocks_schema_errors(self):
        gate_result = quality_gate(
            {
                "meta": {"title": "", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [],
            }
        )
        assert gate_result.passed is False
        assert gate_result.review_required is False
        assert gate_result.summary["error_count"] == 1
        assert gate_result.errors[0].slide_id == "schema"

    def test_quantified_claim_without_data_source_triggers_high_warning(self):
        slide = TitleContentSlide(
            slide_id="s1",
            layout="title_content",
            title="ROI 可提升 35%",
            content=["预计 12 个月内回本。"],
        )
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide],
            )
        )
        evidence_warnings = [w for w in warnings if "no data_sources" in w.message]
        assert len(evidence_warnings) == 1
        assert evidence_warnings[0].warning_level == WARNING_LEVEL_HIGH

    def test_stats_dashboard_without_data_source_requires_review(self):
        gate_result = quality_gate(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    StatsDashboardSlide(
                        slide_id="s1",
                        layout="stats_dashboard",
                        title="经营指标改善",
                        metrics=[
                            MetricEntry(label="收入", value="+18%"),
                            MetricEntry(label="毛利", value="+6pt"),
                        ],
                        insights=["效率改善进入兑现期"],
                    )
                ],
            )
        )
        assert gate_result.passed is True
        assert gate_result.review_required is True
        assert any("no data_sources" in issue.message for issue in gate_result.high)

    def test_two_columns_without_anti_argument_triggers_warning(self):
        slide = TwoColumnsSlide(
            slide_id="s1",
            layout="two_columns",
            title="集中建设与分步推进对比",
            left=ColumnBlock(heading="集中建设", items=["统一平台", "投入较大"]),
            right=ColumnBlock(heading="分步推进", items=["风险更低", "见效较慢"]),
        )
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[slide],
            )
        )
        objection_warnings = [w for w in warnings if "add anti_argument" in w.message]
        assert len(objection_warnings) == 1
        assert objection_warnings[0].warning_level == WARNING_LEVEL_WARNING

    def test_generic_background_opening_triggers_high_warning(self):
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    TitleOnlySlide(slide_id="s1", layout="title_only", title="项目背景"),
                    TitleOnlySlide(slide_id="s2", layout="title_only", title="建议先聚焦一条主链"),
                ],
            )
        )

        opening_warnings = [w for w in warnings if "generic-background" in w.message]
        assert len(opening_warnings) == 1
        assert opening_warnings[0].warning_level == WARNING_LEVEL_HIGH

    def test_generic_thanks_closing_triggers_high_warning(self):
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    SectionBreakSlide(slide_id="s1", layout="section_break", title="结论先行", subtitle="先打通关键链路"),
                    TitleOnlySlide(slide_id="s2", layout="title_only", title="谢谢"),
                ],
            )
        )

        closing_warnings = [w for w in warnings if "generic closing or thanks" in w.message]
        assert len(closing_warnings) == 1
        assert closing_warnings[0].warning_level == WARNING_LEVEL_HIGH

    def test_last_slide_without_action_or_decision_triggers_warning(self):
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    SectionBreakSlide(slide_id="s1", layout="section_break", title="结论先行", subtitle="先打通关键链路"),
                    TitleContentSlide(slide_id="s2", layout="title_content", title="现状分析", content=["问题一", "问题二"]),
                ],
            )
        )

        decision_warnings = [w for w in warnings if "does not clearly express a recommendation" in w.message]
        assert len(decision_warnings) == 1
        assert decision_warnings[0].warning_level == WARNING_LEVEL_WARNING

    def test_repeated_adjacent_content_triggers_warning(self):
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    TitleContentSlide(
                        slide_id="s1",
                        layout="title_content",
                        title="核心判断",
                        content=["统一数据底座支撑跨部门协同", "主链路试点已经验证投入产出"],
                    ),
                    TitleContentSlide(
                        slide_id="s2",
                        layout="title_content",
                        title="重复展开",
                        content=["统一数据底座支撑跨部门协同", "主链路试点已经验证投入产出"],
                    ),
                ],
            )
        )

        overlap_warnings = [w for w in warnings if "adjacent slides repeat" in w.message]
        assert len(overlap_warnings) == 1
        assert overlap_warnings[0].warning_level == WARNING_LEVEL_WARNING

    def test_repeated_title_triggers_warning(self):
        warnings = check_deck_content(
            DeckDocument(
                meta=ThemeMeta(title="Test", theme="business_red"),
                slides=[
                    TitleOnlySlide(slide_id="s1", layout="title_only", title="实施路径"),
                    TimelineSlide(
                        slide_id="s2",
                        layout="timeline",
                        title="实施路径",
                        stages=[{"title": "Q1"}, {"title": "Q2"}],
                    ),
                ],
            )
        )

        title_repeat_warnings = [w for w in warnings if "title repeats an earlier page" in w.message]
        assert len(title_repeat_warnings) == 1
        assert title_repeat_warnings[0].warning_level == WARNING_LEVEL_WARNING
