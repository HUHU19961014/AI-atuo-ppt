import json
import unittest

from tools.sie_autoppt.clarifier import (
    DEFAULT_AUDIENCE_HINT,
    clarify_user_input,
    derive_planning_context,
    load_clarifier_session,
)


class ClarifierTests(unittest.TestCase):
    def test_generic_request_triggers_full_guidance(self):
        result = clarify_user_input("帮我做PPT", prefer_llm=False)

        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.guide_mode, "full")
        self.assertEqual(
            result.missing_dimensions,
            ("purpose", "audience", "slides", "style", "core_content"),
        )
        self.assertIn("直接生成", result.message)

    def test_concrete_topic_triggers_partial_guidance(self):
        result = clarify_user_input("帮我做Q2业绩汇报，5页", prefer_llm=False)

        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.guide_mode, "partial")
        self.assertEqual(result.requirements.topic, "Q2业绩汇报")
        self.assertEqual(result.requirements.chapters, 5)
        self.assertIn("audience", result.missing_dimensions)
        self.assertIn("style", result.missing_dimensions)

    def test_skip_keyword_short_circuits_clarification(self):
        result = clarify_user_input("直接生成，做一份产品方案PPT", prefer_llm=False)

        self.assertEqual(result.status, "skipped")
        self.assertTrue(result.skipped)
        self.assertEqual(result.guide_mode, "none")

    def test_session_resume_merges_previous_answers(self):
        first = clarify_user_input("帮我做Q2业绩汇报，5页", prefer_llm=False)
        restored_session = load_clarifier_session(first.session.to_json())

        second = clarify_user_input(
            "给公司领导看，商务专业风格，重点讲增长数据、技术突破和下阶段计划",
            session=restored_session,
            prefer_llm=False,
        )

        self.assertEqual(second.status, "ready")
        self.assertEqual(second.requirements.topic, "Q2业绩汇报")
        self.assertEqual(second.requirements.audience, "公司领导")
        self.assertEqual(second.requirements.style, "商务专业")
        self.assertIn("增长数据", second.requirements.core_content)
        self.assertEqual(second.requirements.chapters, 5)

    def test_derive_planning_context_enriches_request_fields(self):
        context = derive_planning_context(
            topic="帮我做Q2业绩汇报，5页，给公司领导看，商务专业风格",
            brief="重点讲增长数据、技术突破、下阶段计划",
            audience=DEFAULT_AUDIENCE_HINT,
            prefer_llm=False,
        )

        self.assertEqual(context.status, "ready")
        self.assertEqual(context.topic, "Q2业绩汇报")
        self.assertEqual(context.audience, "公司领导")
        self.assertEqual(context.chapters, 5)
        self.assertIn("商务专业", context.brief)
        self.assertIn("增长数据", context.brief)

    def test_session_json_round_trip_is_stable(self):
        result = clarify_user_input("帮我做PPT", prefer_llm=False)
        loaded = load_clarifier_session(result.session.to_json())

        self.assertEqual(loaded.turn_count, result.session.turn_count)
        self.assertEqual(loaded.pending_dimensions, result.session.pending_dimensions)
        self.assertEqual(json.loads(loaded.to_json())["status"], result.session.status)
