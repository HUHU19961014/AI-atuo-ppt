from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from .io import RenderLog
from .layout_router import render_slide
from .schema import DeckDocument, ValidatedDeck, validate_deck_payload
from .theme_loader import load_theme


@dataclass(frozen=True)
class RenderArtifacts:
    output_path: Path
    log_path: Path | None
    slide_count: int
    warnings: tuple[str, ...] = ()


def _coerce_validated_deck(deck_data: DeckDocument | ValidatedDeck | dict[str, object]) -> ValidatedDeck:
    if isinstance(deck_data, ValidatedDeck):
        return deck_data
    if isinstance(deck_data, DeckDocument):
        return ValidatedDeck(deck=deck_data)
    if isinstance(deck_data, dict):
        return validate_deck_payload(deck_data)
    raise TypeError("deck_data must be a DeckDocument, ValidatedDeck, or JSON object.")


def generate_ppt(
    deck_data: DeckDocument | ValidatedDeck | dict[str, object],
    output_path: str | Path,
    theme_name: str | None = None,
    log_path: str | Path | None = None,
) -> RenderArtifacts:
    validated = _coerce_validated_deck(deck_data)
    deck = validated.deck
    theme = load_theme(theme_name or deck.meta.theme)

    prs = Presentation()
    prs.slide_width = Inches(theme.page.width)
    prs.slide_height = Inches(theme.page.height)

    log = RenderLog()
    log.info(f"deck title: {deck.meta.title}")
    log.info(f"theme: {theme.theme_name}")
    log.extend(validated.warnings)

    for index, slide in enumerate(deck.slides, start=1):
        render_slide(prs, slide, theme, log, index, len(deck.slides))

    final_output = Path(output_path)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(final_output))

    final_log_path = Path(log_path) if log_path else None
    if final_log_path is not None:
        log.write(final_log_path)

    return RenderArtifacts(
        output_path=final_output,
        log_path=final_log_path,
        slide_count=len(deck.slides),
        warnings=tuple(validated.warnings),
    )
