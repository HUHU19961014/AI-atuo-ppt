import unittest

from tools.sie_autoppt.inputs.html_parser import parse_html_payload, validate_payload


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
