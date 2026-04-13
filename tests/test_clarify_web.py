import json
import unittest

from tools.sie_autoppt.clarify_web import run_clarifier_turn
from tools.sie_autoppt.exceptions import ClarifierRequestError


class ClarifyWebTests(unittest.TestCase):
    def test_run_clarifier_turn_rejects_empty_message(self):
        with self.assertRaises(ClarifierRequestError):
            run_clarifier_turn(message="   ")

    def test_run_clarifier_turn_rejects_invalid_session_payload(self):
        with self.assertRaises(ClarifierRequestError):
            run_clarifier_turn(message="Q2 review", session_payload="{invalid")

    def test_run_clarifier_turn_returns_blocking_payload_for_vague_request(self):
        payload = run_clarifier_turn(message="帮我做PPT")

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertTrue(payload["blocking"])
        self.assertEqual(payload["questions"][0]["dimension"], "topic")
        self.assertIn("response_template", payload)

    def test_run_clarifier_turn_supports_session_resume(self):
        first = run_clarifier_turn(message="帮我做PPT")
        second = run_clarifier_turn(
            message="1. Q2经营复盘\n2A\n3A\n4B\n5A\n6A\n7. 重点讲收入增长、重点风险和下季度动作",
            session_payload=json.dumps(first["session"], ensure_ascii=False),
        )

        self.assertEqual(second["status"], "ready")
        self.assertEqual(second["requirements"]["topic"], "Q2经营复盘")
        self.assertEqual(second["requirements"]["purpose"], "工作汇报")
        self.assertEqual(second["requirements"]["audience"], "公司领导")
        self.assertEqual(second["requirements"]["theme"], "sie_consulting_fixed")
