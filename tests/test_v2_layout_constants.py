import unittest

from tools.sie_autoppt.v2.renderers.layout_constants import (
    CARDS_GRID,
    MATRIX_GRID,
    SECTION_BREAK,
    STATS_DASHBOARD,
    TIMELINE,
    TITLE_BAND,
    TITLE_CONTENT,
    TITLE_IMAGE,
    TITLE_ONLY,
    TWO_COLUMNS,
    cards_grid_positions,
)


class V2LayoutConstantsTests(unittest.TestCase):
    def test_title_band_and_core_layouts_expose_expected_geometry(self):
        self.assertEqual(TITLE_BAND.left, 0.78)
        self.assertEqual(TITLE_BAND.top, 0.5)
        self.assertGreater(TITLE_CONTENT.card.width, 11.0)
        self.assertGreater(TITLE_ONLY.card.height, 4.0)
        self.assertGreater(TITLE_IMAGE.right_card.width, TITLE_IMAGE.left_card.width)
        self.assertGreater(TIMELINE.flow_width, 11.0)
        self.assertEqual(SECTION_BREAK.title_top, 1.55)
        self.assertEqual(STATS_DASHBOARD.metrics_top, 1.42)
        self.assertEqual(len(MATRIX_GRID.cell_positions), 4)

    def test_cards_grid_positions_cover_supported_card_counts(self):
        two_cards = cards_grid_positions(2)
        three_cards = cards_grid_positions(3)
        four_cards = cards_grid_positions(4)

        self.assertEqual(len(two_cards), 2)
        self.assertEqual(len(three_cards), 3)
        self.assertEqual(len(four_cards), 4)
        self.assertEqual(two_cards[0][2], TWO_COLUMNS.card_width)
        self.assertEqual(CARDS_GRID.card_title_left_padding, 0.14)
        self.assertEqual(CARDS_GRID.card_body_top_offset, 0.6)


if __name__ == "__main__":
    unittest.main()
