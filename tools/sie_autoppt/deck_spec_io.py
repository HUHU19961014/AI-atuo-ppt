import json
from pathlib import Path

from .models import BodyPageSpec, DeckSpec


DECK_SPEC_SCHEMA_VERSION = "1.0"


def body_page_spec_to_dict(page: BodyPageSpec) -> dict[str, object]:
    return {
        "page_key": page.page_key,
        "title": page.title,
        "subtitle": page.subtitle,
        "bullets": list(page.bullets),
        "pattern_id": page.pattern_id,
        "nav_title": page.nav_title,
        "reference_style_id": page.reference_style_id,
        "payload": dict(page.payload),
    }


def body_page_spec_from_dict(data: dict[str, object]) -> BodyPageSpec:
    return BodyPageSpec(
        page_key=str(data["page_key"]),
        title=str(data["title"]),
        subtitle=str(data.get("subtitle", "")),
        bullets=[str(item) for item in data.get("bullets", [])],
        pattern_id=str(data["pattern_id"]),
        nav_title=str(data.get("nav_title", "")),
        reference_style_id=str(data["reference_style_id"]) if data.get("reference_style_id") else None,
        payload=dict(data.get("payload", {})),
    )


def deck_spec_to_dict(deck: DeckSpec) -> dict[str, object]:
    return {
        "schema_version": DECK_SPEC_SCHEMA_VERSION,
        "cover_title": deck.cover_title,
        "body_pages": [body_page_spec_to_dict(page) for page in deck.body_pages],
    }


def deck_spec_from_dict(data: dict[str, object]) -> DeckSpec:
    body_pages_data = data.get("body_pages", [])
    if not isinstance(body_pages_data, list):
        raise ValueError("Deck spec body_pages must be a list.")
    return DeckSpec(
        cover_title=str(data["cover_title"]),
        body_pages=[body_page_spec_from_dict(page) for page in body_pages_data],
    )


def load_deck_spec(deck_spec_path: Path) -> DeckSpec:
    data = json.loads(deck_spec_path.read_text(encoding="utf-8"))
    return deck_spec_from_dict(data)


def write_deck_spec(deck: DeckSpec, deck_spec_path: Path) -> Path:
    deck_spec_path.parent.mkdir(parents=True, exist_ok=True)
    deck_spec_path.write_text(
        json.dumps(deck_spec_to_dict(deck), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return deck_spec_path
