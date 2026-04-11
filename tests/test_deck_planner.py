import unittest
from unittest.mock import patch

from tools.sie_autoppt.config import INPUT_DIR
from tools.sie_autoppt.pipeline import plan_deck_from_html
from tools.sie_autoppt.planning.deck_planner import (
    _planning_style_context,
    build_deck_spec_from_html,
    build_directory_lines,
    build_directory_window,
    clamp_requested_chapters,
    infer_legacy_requested_chapters,
    resolve_page_layout,
)
from tools.sie_autoppt.planning.pagination import paginate_body_page


class DeckPlannerTests(unittest.TestCase):
    def test_clamp_requested_chapters_respects_bounds(self):
        self.assertEqual(clamp_requested_chapters(None, 3), 3)
        self.assertEqual(clamp_requested_chapters(0, 3), 3)
        self.assertEqual(clamp_requested_chapters(2, 3), 2)
        self.assertEqual(clamp_requested_chapters(99, 3), 3)
        self.assertEqual(clamp_requested_chapters(3, 2), 2)

    def test_standard_html_builds_three_default_pages(self):
        html = (INPUT_DIR / "uat_plan_sample.html").read_text(encoding="utf-8")

        deck = build_deck_spec_from_html(html, chapters=3)

        self.assertEqual(len(deck.body_pages), 3)
        self.assertEqual([page.page_key for page in deck.body_pages], ["overview", "scope", "focus"])
        self.assertEqual([page.content_count for page in deck.body_pages], [len(page.bullets) for page in deck.body_pages])
        self.assertTrue(all(page.slide_role == "body" for page in deck.body_pages))
        self.assertEqual(len(build_directory_lines(deck.body_pages)), 5)

    def test_legacy_html_auto_expands_when_content_is_dense(self):
        html = """
        <div class="title">制造企业数字化升级</div>
        <div class="subtitle">围绕现状、场景、风险与阶段安排进行结构化呈现</div>
        <div class="phase-time">Q1</div><div class="phase-name">规划</div><div class="phase-func">明确蓝图和治理边界</div>
        <div class="phase-time">Q2</div><div class="phase-name">建设</div><div class="phase-func">完成核心流程与主数据打通</div>
        <div class="phase-time">Q3</div><div class="phase-name">试点</div><div class="phase-func">验证跨部门协同效率</div>
        <div class="phase-time">Q4</div><div class="phase-name">推广</div><div class="phase-func">复制到更多工厂与业务单元</div>
        <div class="scenario">采购到库存链路需要统一口径</div>
        <div class="scenario">生产计划与执行之间存在断点</div>
        <div class="scenario">质量追溯依赖人工汇总</div>
        <div class="scenario">海外审计需要可证明的数据链</div>
        <div class="note">项目组织复杂，需设立明确的治理机制</div>
        <div class="note">主数据口径不统一会拖慢实施进度</div>
        <div class="note">需同步设计风险应对与验收标准</div>
        <div class="footer">阶段推进必须和能力沉淀并行。</div>
        """

        deck = build_deck_spec_from_html(html, chapters=None)

        self.assertGreaterEqual(len(deck.body_pages), 4)
        self.assertIn("phases", [page.page_key for page in deck.body_pages])
        self.assertIn("notes", [page.page_key for page in deck.body_pages])
        self.assertIn("process_flow", [page.pattern_id for page in deck.body_pages])
        self.assertIn("org_governance", [page.pattern_id for page in deck.body_pages])

    def test_infer_legacy_requested_chapters_grows_with_content_density(self):
        html = """
        <div class="title">升级项目</div>
        <div class="phase-name">规划</div><div class="phase-func">梳理业务</div>
        <div class="scenario">链路长</div>
        <div class="note">风险高</div>
        """
        from tools.sie_autoppt.inputs.html_parser import parse_html_payload

        payload = parse_html_payload(html)
        self.assertEqual(infer_legacy_requested_chapters(payload), 3)

        dense_html = html + """
        <div class="phase-name">建设</div><div class="phase-func">打通系统</div>
        <div class="phase-name">推广</div><div class="phase-func">复制推广</div>
        <div class="scenario">协同复杂</div>
        <div class="scenario">数据治理要求高</div>
        <div class="scenario">审计频繁</div>
        <div class="note">需要跨部门治理</div>
        <div class="note">需要风险预案</div>
        <div class="footer">补充长说明补充长说明补充长说明补充长说明补充长说明</div>
        """
        dense_payload = parse_html_payload(dense_html)
        self.assertGreaterEqual(infer_legacy_requested_chapters(dense_payload), 4)

    def test_slide_tag_html_uses_all_detected_pages_by_default(self):
        html = """
        <div class="title">Supply Chain Compliance</div>
        <slide data-pattern="general_business">
          <h2>Background</h2>
          <ul><li>Regulation pressure</li></ul>
        </slide>
        <slide data-pattern="process_flow">
          <h2>Roadmap</h2>
          <ul><li>Assess</li><li>Design</li><li>Launch</li></ul>
        </slide>
        <slide>
          <h2>Governance</h2>
          <p>Clarify ownership</p>
        </slide>
        <slide>
          <h2>Summary</h2>
          <p>Close the loop</p>
        </slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)

        self.assertEqual(len(deck.body_pages), 4)
        self.assertEqual([page.page_key for page in deck.body_pages], ["slide_1", "slide_2", "slide_3", "slide_4"])
        self.assertEqual([page.pattern_id for page in deck.body_pages[:2]], ["general_business", "process_flow"])
        self.assertEqual(deck.body_pages[0].layout_variant, "general_business_3")
        self.assertEqual(deck.body_pages[1].layout_variant, "process_flow_3")
        self.assertEqual(deck.body_pages[0].layout_hints["desired_layout_variant"], "general_business_3")
        self.assertEqual(deck.body_pages[1].layout_hints["desired_layout_variant"], "process_flow_3")
        self.assertEqual(deck.body_pages[1].payload["steps"][0]["title"], "Assess")
        self.assertEqual(deck.body_pages[1].content_count, 3)
        self.assertFalse(deck.body_pages[1].is_continuation)
        self.assertEqual(deck.body_pages[1].slide_role, "body")
        self.assertEqual(deck.body_pages[1].layout_hints["density"], "compact")

    def test_slide_tag_html_supports_dashboard_and_roadmap_patterns(self):
        html = """
        <div class="title">Business Review</div>
        <slide data-pattern="kpi_dashboard">
          <h2>经营指标</h2>
          <p class="subtitle">核心 KPI 摘要</p>
          <ul>
            <li>收入增长: 18%</li>
            <li>利润率: 32%</li>
            <li>交付准时率: 96%</li>
            <li>客户满意度: 92%</li>
          </ul>
        </slide>
        <slide data-pattern="roadmap_timeline">
          <h2>年度路线图</h2>
          <p class="subtitle">按季度推进</p>
          <ul>
            <li>Q1: 完成现状诊断</li>
            <li>Q2: 搭建能力底座</li>
            <li>Q3: 推进试点上线</li>
            <li>Q4: 复制推广</li>
          </ul>
        </slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)

        self.assertEqual([page.pattern_id for page in deck.body_pages], ["kpi_dashboard", "roadmap_timeline"])
        self.assertIn("metrics", deck.body_pages[0].payload)
        self.assertIn("stages", deck.body_pages[1].payload)

    def test_slide_tag_html_supports_risk_and_claim_patterns(self):
        html = """
        <div class="title">Arbitration Review</div>
        <slide data-pattern="risk_matrix">
          <h2>风险矩阵</h2>
          <p class="subtitle">核心风险判断</p>
          <ul>
            <li>汇率风险: 影响偿债能力</li>
            <li>政策风险: 影响谈判节奏</li>
            <li>执行风险: 影响项目收益</li>
            <li>声誉风险: 影响后续合作</li>
          </ul>
        </slide>
        <slide data-pattern="claim_breakdown">
          <h2>索赔拆解</h2>
          <p class="subtitle">金额构成</p>
          <ul>
            <li>电费欠款: $2.1B</li>
            <li>违约利息: $1.3B</li>
            <li>汇率损失: $0.8B</li>
            <li>其他费用: $0.3B</li>
          </ul>
        </slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)

        self.assertEqual([page.pattern_id for page in deck.body_pages], ["risk_matrix", "claim_breakdown"])
        self.assertIn("items", deck.body_pages[0].payload)
        self.assertIn("claims", deck.body_pages[1].payload)

    def test_card_analysis_html_uses_reference_styles(self):
        html = (INPUT_DIR / "ai_pythonpptx_strategy.html").read_text(encoding="utf-8")

        deck = build_deck_spec_from_html(html, chapters=3)

        self.assertEqual(
            [page.reference_style_id for page in deck.body_pages],
            ["comparison_upgrade", "capability_ring", "five_phase_path"],
        )
        self.assertEqual(
            [page.pattern_id for page in deck.body_pages],
            ["comparison_upgrade", "capability_ring", "five_phase_path"],
        )
        self.assertEqual([page.content_count for page in deck.body_pages], [6, 7, 4])

    def test_pipeline_returns_matching_pattern_ids_and_directory_lines(self):
        plan = plan_deck_from_html(INPUT_DIR / "architecture_program_sample.html", chapters=3)

        self.assertEqual(len(plan.pattern_ids), len(plan.deck.body_pages))
        self.assertEqual(plan.pattern_ids, [page.pattern_id for page in plan.deck.body_pages])
        self.assertEqual(len(plan.chapter_lines), 5)
        self.assertEqual(plan.chapter_lines[-1], "Q&A")

    def test_directory_window_moves_with_active_page_after_five_pages(self):
        html = """
        <slide><h2>Page 1</h2><p>A</p></slide>
        <slide><h2>Page 2</h2><p>B</p></slide>
        <slide><h2>Page 3</h2><p>C</p></slide>
        <slide><h2>Page 4</h2><p>D</p></slide>
        <slide><h2>Page 5</h2><p>E</p></slide>
        <slide><h2>Page 6</h2><p>F</p></slide>
        <slide><h2>Page 7</h2><p>G</p></slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)
        lines, active_index = build_directory_window(deck.body_pages, 6)

        self.assertEqual(lines, ["Page3", "Page4", "Page5", "Page6", "Page7"])
        self.assertEqual(active_index, 4)

    def test_pcb_sample_builds_structured_payloads_for_renderers(self):
        html = (INPUT_DIR / "pcb_erp_general_solution.html").read_text(encoding="utf-8")

        deck = build_deck_spec_from_html(html, chapters=3)

        self.assertEqual(
            [page.pattern_id for page in deck.body_pages],
            ["solution_architecture", "process_flow", "org_governance"],
        )
        self.assertIsNone(deck.body_pages[0].layout_variant)
        self.assertEqual(deck.body_pages[1].layout_variant, "process_flow_5")
        self.assertIsNone(deck.body_pages[2].layout_variant)
        self.assertEqual(deck.body_pages[1].layout_hints["desired_layout_variant"], "process_flow_5")
        self.assertEqual(deck.body_pages[2].layout_hints["desired_capacity"], 5)
        self.assertEqual(deck.body_pages[2].layout_hints["desired_layout_variant"], "")
        self.assertEqual(len(deck.body_pages[0].payload.get("layers", [])), 4)
        self.assertEqual(len(deck.body_pages[1].payload.get("steps", [])), 4)
        self.assertEqual(deck.body_pages[2].payload.get("label_prefix"), "重点")
        self.assertTrue(deck.body_pages[2].payload.get("footer_text"))

    def test_choose_page_pattern_prefers_dashboard_keywords(self):
        pattern_id, _, _, _ = resolve_page_layout(
            "kpi_dashboard",
            "经营指标仪表盘",
            ["收入增长: 18%", "利润提升: 6%"],
        )

        self.assertEqual(pattern_id, "kpi_dashboard")

    def test_choose_page_pattern_prefers_risk_keywords(self):
        pattern_id, _, _, _ = resolve_page_layout(
            "risk_matrix",
            "风险矩阵评估",
            ["汇率风险", "政策风险"],
        )

        self.assertEqual(pattern_id, "risk_matrix")

    def test_paginate_body_page_creates_continuation_metadata(self):
        from tools.sie_autoppt.models import BodyPageSpec

        page = BodyPageSpec(
            page_key="scope",
            title="Scope",
            subtitle="Subtitle",
            bullets=["A", "B", "C", "D", "E", "F"],
            pattern_id="process_flow",
            nav_title="Scope",
            slide_role="body",
            layout_variant="process_flow_5",
        )

        pages = paginate_body_page(page, max_items_per_page=5)

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].source_item_range, (0, 5))
        self.assertEqual(pages[1].page_key, "scope_cont_2")
        self.assertTrue(pages[1].is_continuation)
        self.assertEqual(pages[1].continuation_index, 2)
        self.assertEqual(pages[1].source_item_range, (5, 6))

    def test_slide_tag_html_paginate_overflow_into_continuation_pages(self):
        html = """
        <div class="title">Program</div>
        <slide data-pattern="process_flow">
          <h2>Roadmap</h2>
          <ul>
            <li>Assess current process dependencies across regions</li>
            <li>Design target operating flow with governance controls</li>
            <li>Align governance checkpoints with program milestones</li>
            <li>Prepare migration runbook for cutover readiness</li>
            <li>Execute pilot launch with cross-team command center</li>
            <li>Scale to remaining sites with controlled rollout waves</li>
            <li>Stabilize support model after go-live transition</li>
            <li>Capture KPI baseline for benefits tracking</li>
            <li>Expand controls to supplier collaboration touchpoints</li>
            <li>Close lessons learned and institutionalize playbook</li>
          </ul>
        </slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)

        self.assertEqual(len(deck.body_pages), 2)
        self.assertEqual(deck.body_pages[0].page_key, "slide_1")
        self.assertEqual(deck.body_pages[0].source_item_range, (0, 9))
        self.assertFalse(deck.body_pages[0].is_continuation)
        self.assertEqual(deck.body_pages[0].layout_variant, "process_flow_9")
        self.assertEqual(deck.body_pages[0].layout_hints["desired_layout_variant"], "process_flow_9")
        self.assertEqual(deck.body_pages[1].page_key, "slide_1_cont_2")
        self.assertTrue(deck.body_pages[1].is_continuation)
        self.assertEqual(deck.body_pages[1].continuation_index, 2)
        self.assertEqual(deck.body_pages[1].source_item_range, (9, 10))
        self.assertEqual(deck.body_pages[1].layout_variant, "process_flow_3")
        self.assertEqual(deck.body_pages[1].layout_hints["desired_layout_variant"], "process_flow_3")

    def test_directory_lines_ignore_continuation_pages(self):
        html = """
        <slide><h2>Page 1</h2><ul>
          <li>Assess current process dependencies across regions</li>
          <li>Design target operating flow with governance controls</li>
          <li>Align governance checkpoints with program milestones</li>
          <li>Prepare migration runbook for cutover readiness</li>
          <li>Execute pilot launch with cross-team command center</li>
          <li>Scale to remaining sites with controlled rollout waves</li>
          <li>Stabilize support model after go-live transition</li>
          <li>Capture KPI baseline for benefits tracking</li>
          <li>Expand controls to supplier collaboration touchpoints</li>
          <li>Close lessons learned and institutionalize playbook</li>
        </ul></slide>
        <slide><h2>Page 2</h2><p>B</p></slide>
        <slide><h2>Page 3</h2><p>C</p></slide>
        <slide><h2>Page 4</h2><p>D</p></slide>
        <slide><h2>Page 5</h2><p>E</p></slide>
        """

        deck = build_deck_spec_from_html(html, chapters=None)
        lines = build_directory_lines(deck.body_pages)
        window_lines, active_index = build_directory_window(deck.body_pages, 1)

        self.assertEqual(lines, ["Page1", "Page2", "Page3", "Page4", "Page5"])
        self.assertEqual(window_lines, ["Page1", "Page2", "Page3", "Page4", "Page5"])
        self.assertEqual(active_index, 0)

    def test_resolve_page_layout_falls_back_when_manifest_is_unavailable(self):
        with patch("tools.sie_autoppt.planning.deck_planner.load_template_manifest", side_effect=FileNotFoundError("missing")):
            _planning_style_context.cache_clear()
            pattern_id, layout_variant, layout_hints, max_items = resolve_page_layout(
                "process_flow",
                "Roadmap",
                ["A", "B", "C", "D"],
            )
            _planning_style_context.cache_clear()

        self.assertEqual(pattern_id, "process_flow")
        self.assertIsNone(layout_variant)
        self.assertEqual(layout_hints["desired_capacity"], 5)
        self.assertEqual(layout_hints["desired_layout_variant"], "")
        self.assertEqual(max_items, 5)
