from pathlib import Path

from ..deck_spec_io import load_deck_spec
from ..models import DeckPlan
from ..planning.deck_planner import build_deck_spec_from_html, build_directory_lines


def build_deck_plan(deck) -> DeckPlan:
    body_pages = deck.body_pages
    return DeckPlan(
        deck=deck,
        chapter_lines=build_directory_lines(body_pages),
        pattern_ids=[page.pattern_id for page in body_pages],
    )


def plan_deck_from_html(html_path: Path, chapters: int | None = None) -> DeckPlan:
    html = html_path.read_text(encoding="utf-8")
    deck = build_deck_spec_from_html(html, chapters)
    return build_deck_plan(deck)


def plan_deck_from_json(deck_spec_path: Path) -> DeckPlan:
    deck = load_deck_spec(deck_spec_path)
    return build_deck_plan(deck)


__all__ = ["build_deck_plan", "plan_deck_from_html", "plan_deck_from_json"]
