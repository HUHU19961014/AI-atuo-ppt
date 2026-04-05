import json
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.config import INPUT_DIR
from tools.sie_autoppt.deck_spec_io import DECK_SPEC_SCHEMA_VERSION, load_deck_spec, write_deck_spec
from tools.sie_autoppt.pipeline import plan_deck_from_html, plan_deck_from_json


class DeckSpecIoTests(unittest.TestCase):
    def test_deck_spec_round_trip_preserves_pages(self):
        plan = plan_deck_from_html(INPUT_DIR / "pcb_erp_general_solution.html", chapters=3)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "deck_spec.json"
            write_deck_spec(plan.deck, output_path)

            self.assertTrue(output_path.exists())
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], DECK_SPEC_SCHEMA_VERSION)

            loaded = load_deck_spec(output_path)
            self.assertEqual(loaded.cover_title, plan.deck.cover_title)
            self.assertEqual([page.pattern_id for page in loaded.body_pages], [page.pattern_id for page in plan.deck.body_pages])
            self.assertEqual(loaded.body_pages[0].payload, plan.deck.body_pages[0].payload)

    def test_plan_deck_from_json_rebuilds_directory_lines(self):
        plan = plan_deck_from_html(INPUT_DIR / "architecture_program_sample.html", chapters=3)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "deck_spec.json"
            write_deck_spec(plan.deck, output_path)

            json_plan = plan_deck_from_json(output_path)
            self.assertEqual(json_plan.pattern_ids, plan.pattern_ids)
            self.assertEqual(json_plan.chapter_lines, plan.chapter_lines)

