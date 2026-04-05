import unittest

from tools.sie_autoppt.inputs.html_parser import (
    extract_list_items_from_block,
    extract_steps,
    extract_tag_inside_block,
    parse_html_payload,
    validate_payload,
)


class HtmlParserTests(unittest.TestCase):
    def test_parse_html_payload_extracts_core_fields(self):
        html = """
        <div class="title">Program Rollout</div>
        <div class="subtitle">Delivery overview</div>
        <div class="scope-title">Scope Title</div>
        <div class="scope-subtitle">Scope Subtitle</div>
        <div class="focus-title">Focus Title</div>
        <div class="focus-subtitle">Focus Subtitle</div>
        <div class="phase-time">Week 1</div>
        <div class="phase-name">Design</div>
        <div class="phase-code">D-01</div>
        <div class="phase-func">Define operating model</div>
        <div class="phase-owner">PMO</div>
        <div class="phase-time">Week 2</div>
        <div class="phase-name">Build</div>
        <div class="phase-code">B-02</div>
        <div class="phase-func">Implement templates</div>
        <div class="scenario">Scenario A</div>
        <div class="scenario">Scenario B</div>
        <div class="note">Important note</div>
        <div class="footer">Project footer</div>
        """

        payload = parse_html_payload(html)

        self.assertEqual(payload.title, "Program Rollout")
        self.assertEqual(payload.subtitle, "Delivery overview")
        self.assertEqual(payload.scope_title, "Scope Title")
        self.assertEqual(payload.focus_subtitle, "Focus Subtitle")
        self.assertEqual(len(payload.phases), 2)
        self.assertEqual(payload.phases[0]["owner"], "PMO")
        self.assertEqual(payload.phases[1]["owner"], "")
        self.assertEqual(payload.scenarios, ["Scenario A", "Scenario B"])
        self.assertEqual(payload.notes, ["Important note"])
        self.assertEqual(payload.footer, "Project footer")

    def test_validate_payload_rejects_empty_html(self):
        payload = parse_html_payload("<html><body></body></html>")
        with self.assertRaises(ValueError):
            validate_payload(payload)

    def test_validate_payload_requires_body_content(self):
        payload = parse_html_payload('<div class="title">Only title</div>')
        with self.assertRaises(ValueError):
            validate_payload(payload)

    def test_parser_handles_nested_markup_and_class_order(self):
        html = """
        <section class="panel hero title-block">
          <h2 class="subtitle extra">Executive Subtitle</h2>
          <div class="x title y"><span>Program</span> <strong>Overview</strong></div>
          <div class="phase-name"><span>Discover</span></div>
          <div class="phase-func"><em>Clarify baseline</em></div>
          <div class="scenario"><span>Scenario</span> A</div>
          <div class="note">Risk <strong>watch</strong></div>
        </section>
        """

        payload = parse_html_payload(html)

        self.assertEqual(payload.title, "Program Overview")
        self.assertEqual(payload.subtitle, "Executive Subtitle")
        self.assertEqual(payload.phases[0]["name"], "Discover")
        self.assertEqual(payload.phases[0]["func"], "Clarify baseline")
        self.assertEqual(payload.scenarios, ["Scenario A"])
        self.assertEqual(payload.notes, ["Risk watch"])

    def test_block_extractors_handle_multi_class_blocks(self):
        html = """
        <div class="card card-danger">
          <h2><span>01</span> 关键风险</h2>
          <ul>
            <li><strong>风险一</strong>：说明</li>
            <li>风险二</li>
          </ul>
        </div>
        <div class="step">
          <div class="step-number">1</div>
          <h3><span>阶段一</span></h3>
          <p>梳理现状与目标</p>
        </div>
        """

        self.assertEqual(extract_tag_inside_block(html, "card card-danger", "h2"), "01 关键风险")
        self.assertEqual(extract_list_items_from_block(html, "card card-danger"), ["风险一：说明", "风险二"])
        self.assertEqual(extract_steps(html), [("阶段一", "梳理现状与目标")])
