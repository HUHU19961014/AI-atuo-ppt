from pathlib import Path

from .models import DeckPlan
from .planning.deck_planner import build_deck_spec_from_html, build_directory_lines


def plan_deck_from_html(html_path: Path, chapters: int) -> DeckPlan:
    html = html_path.read_text(encoding="utf-8")
    deck = build_deck_spec_from_html(html, chapters)
    body_pages = deck.body_pages
    return DeckPlan(
        deck=deck,
        chapter_lines=build_directory_lines(body_pages),
        pattern_ids=[page.pattern_id for page in body_pages],
    )
